from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from silly_teamwork.ai.llm import MockProvider
from silly_teamwork.ai.service import AIAssistantService, get_ai_assistant_service
from silly_teamwork.ai.tools import AIToolLayer
from silly_teamwork.core.security import create_access_token, hash_password
from silly_teamwork.db.base import Base
from silly_teamwork.db.session import get_db_session
from silly_teamwork.main import app
from silly_teamwork.models import (
    Project,
    ProjectMember,
    ProjectRole,
    Team,
    TeamMember,
    TeamRole,
    User,
)

pytestmark = pytest.mark.asyncio


@dataclass(frozen=True, slots=True)
class AIRiskApiContext:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]
    leader: User
    member: User
    outsider: User
    project: Project
    leader_headers: dict[str, str]
    member_headers: dict[str, str]
    outsider_headers: dict[str, str]


@pytest_asyncio.fixture
async def ai_risk_api_context() -> AsyncIterator[AIRiskApiContext]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with factory.begin() as session:
        leader = User(username="ai_api_leader", password_hash=hash_password("password"))
        member = User(username="ai_api_member", password_hash=hash_password("password"))
        outsider = User(username="ai_api_outsider", password_hash=hash_password("password"))
        session.add_all([leader, member, outsider])
        await session.flush()
        team = Team(name="AI API Course Team", created_by_id=leader.id)
        session.add(team)
        await session.flush()
        session.add_all(
            [
                TeamMember(team_id=team.id, user_id=leader.id, role=TeamRole.OWNER),
                TeamMember(team_id=team.id, user_id=member.id, role=TeamRole.MEMBER),
            ]
        )
        project = Project(
            team_id=team.id,
            created_by_id=leader.id,
            name="AI API Project",
            status="active",
        )
        session.add(project)
        await session.flush()
        session.add_all(
            [
                ProjectMember(
                    project_id=project.id,
                    user_id=leader.id,
                    role=ProjectRole.OWNER,
                ),
                ProjectMember(
                    project_id=project.id,
                    user_id=member.id,
                    role=ProjectRole.MEMBER,
                ),
            ]
        )

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_ai_assistant_service] = lambda: AIAssistantService(
        provider=MockProvider(
            default_response=json.dumps(
                {
                    "risk_level": "medium",
                    "summary": "项目存在一定风险",
                    "reasons": ["部分任务临近截止"],
                    "suggestions": ["调整任务优先级"],
                }
            )
        ),
        tool_layer=AIToolLayer(),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield AIRiskApiContext(
            client=client,
            session_factory=factory,
            leader=leader,
            member=member,
            outsider=outsider,
            project=project,
            leader_headers={"Authorization": f"Bearer {create_access_token(str(leader.id))}"},
            member_headers={"Authorization": f"Bearer {create_access_token(str(member.id))}"},
            outsider_headers={"Authorization": f"Bearer {create_access_token(str(outsider.id))}"},
        )

    app.dependency_overrides.clear()
    await engine.dispose()


def _url(project_id: UUID) -> str:
    return f"/api/v1/projects/{project_id}/ai/risk-analysis"


async def test_project_member_can_analyze_risk(ai_risk_api_context: AIRiskApiContext) -> None:
    response = await ai_risk_api_context.client.post(
        _url(ai_risk_api_context.project.id),
        headers=ai_risk_api_context.member_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == str(ai_risk_api_context.project.id)
    assert payload["risk_level"] == "medium"
    assert payload["summary"] == "项目存在一定风险"
    assert payload["reasons"] == ["部分任务临近截止"]
    assert payload["suggestions"] == ["调整任务优先级"]
    assert payload["generated_at"]


async def test_project_leader_can_analyze_risk(ai_risk_api_context: AIRiskApiContext) -> None:
    response = await ai_risk_api_context.client.post(
        _url(ai_risk_api_context.project.id),
        headers=ai_risk_api_context.leader_headers,
    )

    assert response.status_code == 200
    assert response.json()["risk_level"] == "medium"


async def test_non_project_member_gets_forbidden(
    ai_risk_api_context: AIRiskApiContext,
) -> None:
    response = await ai_risk_api_context.client.post(
        _url(ai_risk_api_context.project.id),
        headers=ai_risk_api_context.outsider_headers,
    )

    assert response.status_code == 403


async def test_unauthenticated_request_gets_unauthorized(
    ai_risk_api_context: AIRiskApiContext,
) -> None:
    response = await ai_risk_api_context.client.post(
        _url(ai_risk_api_context.project.id),
    )

    assert response.status_code == 401


async def test_mock_llm_normal_response(
    ai_risk_api_context: AIRiskApiContext,
) -> None:
    response = await ai_risk_api_context.client.post(
        _url(ai_risk_api_context.project.id),
        headers=ai_risk_api_context.member_headers,
    )

    assert response.status_code == 200
    assert response.json()["risk_level"] in {"high", "medium", "low"}


async def test_llm_error_returns_bad_gateway(
    ai_risk_api_context: AIRiskApiContext,
) -> None:
    app.dependency_overrides[get_ai_assistant_service] = lambda: AIAssistantService(
        provider=MockProvider(default_response="not-json"),
        tool_layer=AIToolLayer(),
    )
    try:
        response = await ai_risk_api_context.client.post(
            _url(ai_risk_api_context.project.id),
            headers=ai_risk_api_context.member_headers,
        )
    finally:
        app.dependency_overrides[get_ai_assistant_service] = lambda: AIAssistantService(
            provider=MockProvider(
                default_response=json.dumps(
                    {
                        "risk_level": "medium",
                        "summary": "项目存在一定风险",
                        "reasons": ["部分任务临近截止"],
                        "suggestions": ["调整任务优先级"],
                    }
                )
            ),
            tool_layer=AIToolLayer(),
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "AI service temporarily unavailable"
