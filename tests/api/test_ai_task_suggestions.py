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
class AITaskSuggestionApiContext:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]
    leader: User
    member: User
    outsider: User
    project: Project
    member_headers: dict[str, str]
    outsider_headers: dict[str, str]


def _default_suggestion_payload() -> dict[str, object]:
    return {
        "suggestions": [
            {
                "title": "撰写开题报告",
                "description": "完成课程论文开题",
                "priority": "high",
                "starts_at": "2026-08-20T00:00:00Z",
                "due_at": "2026-08-25T00:00:00Z",
                "recommended_owner_user_id": "00000000-0000-0000-0000-000000000000",
                "reason": "该成员当前任务较少",
            }
        ]
    }


@pytest_asyncio.fixture
async def ai_task_suggestion_api_context() -> AsyncIterator[AITaskSuggestionApiContext]:
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
        leader = User(username="ai_task_leader", password_hash=hash_password("password"))
        member = User(username="ai_task_member", password_hash=hash_password("password"))
        outsider = User(username="ai_task_outsider", password_hash=hash_password("password"))
        session.add_all([leader, member, outsider])
        await session.flush()
        team = Team(name="AI Task Course Team", created_by_id=leader.id)
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
            name="AI Task Project",
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
        provider=MockProvider(default_response=json.dumps(_default_suggestion_payload())),
        tool_layer=AIToolLayer(),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield AITaskSuggestionApiContext(
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


def _url(project_id: UUID) -> str:
    return f"/api/v1/projects/{project_id}/ai/task-suggestions"


async def test_project_member_gets_task_suggestions(
    ai_task_suggestion_api_context: AITaskSuggestionApiContext,
) -> None:
    response = await ai_task_suggestion_api_context.client.post(
        _url(ai_task_suggestion_api_context.project.id),
        headers=ai_task_suggestion_api_context.member_headers,
        json={"instruction": "帮我规划一个课程论文项目", "count": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == str(ai_task_suggestion_api_context.project.id)
    assert len(payload["suggestions"]) == 1
    suggestion = payload["suggestions"][0]
    assert suggestion["title"] == "撰写开题报告"
    assert suggestion["priority"] == "high"
    assert suggestion["due_at"] == "2026-08-25T00:00:00Z"
    assert suggestion["reason"] == "该成员当前任务较少"


async def test_non_project_member_gets_forbidden(
    ai_task_suggestion_api_context: AITaskSuggestionApiContext,
) -> None:
    response = await ai_task_suggestion_api_context.client.post(
        _url(ai_task_suggestion_api_context.project.id),
        headers=ai_task_suggestion_api_context.outsider_headers,
        json={"instruction": "帮我规划任务", "count": 1},
    )

    assert response.status_code == 403


async def test_unauthenticated_request_gets_unauthorized(
    ai_task_suggestion_api_context: AITaskSuggestionApiContext,
) -> None:
    response = await ai_task_suggestion_api_context.client.post(
        _url(ai_task_suggestion_api_context.project.id),
        json={"instruction": "帮我规划任务", "count": 1},
    )

    assert response.status_code == 401


async def test_missing_instruction_returns_validation_error(
    ai_task_suggestion_api_context: AITaskSuggestionApiContext,
) -> None:
    response = await ai_task_suggestion_api_context.client.post(
        _url(ai_task_suggestion_api_context.project.id),
        headers=ai_task_suggestion_api_context.member_headers,
        json={"count": 1},
    )

    assert response.status_code == 422


async def test_invalid_count_returns_validation_error(
    ai_task_suggestion_api_context: AITaskSuggestionApiContext,
) -> None:
    response = await ai_task_suggestion_api_context.client.post(
        _url(ai_task_suggestion_api_context.project.id),
        headers=ai_task_suggestion_api_context.member_headers,
        json={"instruction": "帮我规划任务", "count": 0},
    )

    assert response.status_code == 422


async def test_llm_error_returns_bad_gateway(
    ai_task_suggestion_api_context: AITaskSuggestionApiContext,
) -> None:
    app.dependency_overrides[get_ai_assistant_service] = lambda: AIAssistantService(
        provider=MockProvider(default_response="not-json"),
        tool_layer=AIToolLayer(),
    )
    try:
        response = await ai_task_suggestion_api_context.client.post(
            _url(ai_task_suggestion_api_context.project.id),
            headers=ai_task_suggestion_api_context.member_headers,
            json={"instruction": "帮我规划任务", "count": 1},
        )
    finally:
        app.dependency_overrides[get_ai_assistant_service] = lambda: AIAssistantService(
            provider=MockProvider(
                default_response=json.dumps(_default_suggestion_payload())
            ),
            tool_layer=AIToolLayer(),
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "AI service temporarily unavailable"
