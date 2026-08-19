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
class AIHistoryApiContext:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]
    leader: User
    member: User
    outsider: User
    project: Project
    member_headers: dict[str, str]
    outsider_headers: dict[str, str]


def _risk_payload(summary: str = "项目风险较低") -> str:
    return json.dumps(
        {
            "risk_level": "low",
            "summary": summary,
            "reasons": [],
            "suggestions": [],
        }
    )


def _task_payload() -> str:
    return json.dumps(
        {
            "suggestions": [
                {
                    "title": "撰写报告",
                    "description": None,
                    "priority": "medium",
                    "starts_at": None,
                    "due_at": None,
                    "recommended_owner_user_id": None,
                    "reason": "基础任务",
                }
            ]
        }
    )


def _weekly_payload() -> str:
    return json.dumps(
        {
            "summary": "本周正常",
            "highlights": [],
            "risks": [],
            "suggestions": [],
        }
    )


@pytest_asyncio.fixture
async def ai_history_api_context() -> AsyncIterator[AIHistoryApiContext]:
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
        leader = User(username="ai_history_leader", password_hash=hash_password("password"))
        member = User(username="ai_history_member", password_hash=hash_password("password"))
        outsider = User(username="ai_history_outsider", password_hash=hash_password("password"))
        session.add_all([leader, member, outsider])
        await session.flush()
        team = Team(name="AI History Course Team", created_by_id=leader.id)
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
            name="AI History Project",
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

    provider = MockProvider(
        responses=[_risk_payload(), _task_payload(), _weekly_payload()]
    )
    service = AIAssistantService(provider=provider, tool_layer=AIToolLayer())
    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_ai_assistant_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield AIHistoryApiContext(
            client=client,
            session_factory=factory,
            leader=leader,
            member=member,
            outsider=outsider,
            project=project,
            member_headers={"Authorization": f"Bearer {create_access_token(str(member.id))}"},
            outsider_headers={"Authorization": f"Bearer {create_access_token(str(outsider.id))}"},
        )

    app.dependency_overrides.clear()
    await engine.dispose()


def _history_url(project_id: UUID) -> str:
    return f"/api/v1/projects/{project_id}/ai/history"


async def test_empty_history_returns_null_fields(
    ai_history_api_context: AIHistoryApiContext,
) -> None:
    response = await ai_history_api_context.client.get(
        _history_url(ai_history_api_context.project.id),
        headers=ai_history_api_context.member_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"risk_analysis": None, "task_suggestions": None, "weekly_report": None}


async def test_history_returns_latest_for_each_type(
    ai_history_api_context: AIHistoryApiContext,
) -> None:
    client = ai_history_api_context.client
    project_id = ai_history_api_context.project.id
    headers = ai_history_api_context.member_headers

    for path in (
        f"/api/v1/projects/{project_id}/ai/risk-analysis",
        f"/api/v1/projects/{project_id}/ai/task-suggestions",
        f"/api/v1/projects/{project_id}/ai/weekly-report",
    ):
        body = (
            {"instruction": "规划任务", "count": 1}
            if path.endswith("task-suggestions")
            else {}
        )
        response = await client.post(path, headers=headers, json=body)
        assert response.status_code == 200, response.text

    response = await client.get(_history_url(project_id), headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["risk_analysis"] is not None
    assert payload["task_suggestions"] is not None
    assert payload["weekly_report"] is not None


async def test_history_returns_latest_after_multiple_generations(
    ai_history_api_context: AIHistoryApiContext,
) -> None:
    client = ai_history_api_context.client
    project_id = ai_history_api_context.project.id
    headers = ai_history_api_context.member_headers

    # Consume the first risk response and then the second one.
    response = await client.post(
        f"/api/v1/projects/{project_id}/ai/risk-analysis",
        headers=headers,
        json={},
    )
    assert response.status_code == 200
    second_provider = MockProvider(default_response=_risk_payload("第二次分析"))
    app.dependency_overrides[get_ai_assistant_service] = lambda: AIAssistantService(
        provider=second_provider,
        tool_layer=AIToolLayer(),
    )
    response = await client.post(
        f"/api/v1/projects/{project_id}/ai/risk-analysis",
        headers=headers,
        json={},
    )
    assert response.status_code == 200
    assert response.json()["summary"] == "第二次分析"

    history_response = await client.get(_history_url(project_id), headers=headers)
    assert history_response.status_code == 200
    assert history_response.json()["risk_analysis"]["summary"] == "第二次分析"


async def test_non_project_member_gets_forbidden(
    ai_history_api_context: AIHistoryApiContext,
) -> None:
    response = await ai_history_api_context.client.get(
        _history_url(ai_history_api_context.project.id),
        headers=ai_history_api_context.outsider_headers,
    )

    assert response.status_code == 403


async def test_unauthenticated_request_gets_unauthorized(
    ai_history_api_context: AIHistoryApiContext,
) -> None:
    response = await ai_history_api_context.client.get(
        _history_url(ai_history_api_context.project.id),
    )

    assert response.status_code == 401
