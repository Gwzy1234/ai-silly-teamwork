from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
    AttachmentMode,
    File,
    Project,
    ProjectMember,
    ProjectRole,
    Task,
    TaskMember,
    TaskRole,
    TaskStatus,
    TaskType,
    Team,
    TeamMember,
    TeamRole,
    User,
)

pytestmark = pytest.mark.asyncio


@dataclass(frozen=True, slots=True)
class AIWeeklyReportApiContext:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]
    leader: User
    member: User
    outsider: User
    project: Project
    member_headers: dict[str, str]
    outsider_headers: dict[str, str]


def _default_report_payload() -> dict[str, object]:
    return {
        "summary": "本周项目推进正常",
        "highlights": ["完成文献收集"],
        "risks": ["下周截止任务较多"],
        "suggestions": ["提前开始撰写"],
    }


@pytest_asyncio.fixture
async def ai_weekly_report_api_context() -> AsyncIterator[AIWeeklyReportApiContext]:
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
        leader = User(username="ai_weekly_leader", password_hash=hash_password("password"))
        member = User(username="ai_weekly_member", password_hash=hash_password("password"))
        outsider = User(username="ai_weekly_outsider", password_hash=hash_password("password"))
        session.add_all([leader, member, outsider])
        await session.flush()
        team = Team(name="AI Weekly Course Team", created_by_id=leader.id)
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
            name="AI Weekly Project",
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

        done_task = Task(
            project_id=project.id,
            created_by_id=leader.id,
            title="Finished Draft",
            status=TaskStatus.DONE,
            task_type=TaskType.COLLABORATIVE,
            attachment_mode=AttachmentMode.SHARED,
            completed_at=datetime.now(UTC),
        )
        session.add(done_task)
        await session.flush()
        session.add(
            TaskMember(task_id=done_task.id, user_id=member.id, role=TaskRole.OWNER)
        )

        open_task = Task(
            project_id=project.id,
            created_by_id=leader.id,
            title="Pending Review",
            status=TaskStatus.IN_PROGRESS,
            task_type=TaskType.COLLABORATIVE,
            attachment_mode=AttachmentMode.SHARED,
            due_at=datetime.now(UTC) + timedelta(days=3),
        )
        session.add(open_task)
        await session.flush()
        session.add(
            TaskMember(task_id=open_task.id, user_id=member.id, role=TaskRole.OWNER)
        )

        session.add(
            File(
                project_id=project.id,
                uploaded_by_id=member.id,
                original_name="weekly-notes.pdf",
                storage_key="weekly-notes.pdf",
                content_type="application/pdf",
                size_bytes=1024,
            )
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
        provider=MockProvider(default_response=json.dumps(_default_report_payload())),
        tool_layer=AIToolLayer(),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield AIWeeklyReportApiContext(
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
    return f"/api/v1/projects/{project_id}/ai/weekly-report"


async def test_project_member_generates_weekly_report(
    ai_weekly_report_api_context: AIWeeklyReportApiContext,
) -> None:
    response = await ai_weekly_report_api_context.client.post(
        _url(ai_weekly_report_api_context.project.id),
        headers=ai_weekly_report_api_context.member_headers,
        json={"start_date": "2026-08-12", "end_date": "2026-08-19"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == str(ai_weekly_report_api_context.project.id)
    assert payload["period_start"] == "2026-08-12"
    assert payload["period_end"] == "2026-08-19"
    assert payload["summary"] == "本周项目推进正常"
    assert len(payload["completed_tasks"]) == 1
    assert len(payload["unfinished_tasks"]) == 1
    assert len(payload["overdue_tasks"]) == 0
    assert len(payload["file_updates"]) == 1
    assert payload["risks"] == ["下周截止任务较多"]


async def test_weekly_report_defaults_to_last_seven_days(
    ai_weekly_report_api_context: AIWeeklyReportApiContext,
) -> None:
    response = await ai_weekly_report_api_context.client.post(
        _url(ai_weekly_report_api_context.project.id),
        headers=ai_weekly_report_api_context.member_headers,
        json={},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["period_start"] <= payload["period_end"]


async def test_non_project_member_gets_forbidden(
    ai_weekly_report_api_context: AIWeeklyReportApiContext,
) -> None:
    response = await ai_weekly_report_api_context.client.post(
        _url(ai_weekly_report_api_context.project.id),
        headers=ai_weekly_report_api_context.outsider_headers,
        json={},
    )

    assert response.status_code == 403


async def test_unauthenticated_request_gets_unauthorized(
    ai_weekly_report_api_context: AIWeeklyReportApiContext,
) -> None:
    response = await ai_weekly_report_api_context.client.post(
        _url(ai_weekly_report_api_context.project.id),
        json={},
    )

    assert response.status_code == 401


async def test_invalid_date_range_returns_bad_request(
    ai_weekly_report_api_context: AIWeeklyReportApiContext,
) -> None:
    response = await ai_weekly_report_api_context.client.post(
        _url(ai_weekly_report_api_context.project.id),
        headers=ai_weekly_report_api_context.member_headers,
        json={"start_date": "2026-08-20", "end_date": "2026-08-19"},
    )

    assert response.status_code == 400


async def test_llm_error_returns_bad_gateway(
    ai_weekly_report_api_context: AIWeeklyReportApiContext,
) -> None:
    app.dependency_overrides[get_ai_assistant_service] = lambda: AIAssistantService(
        provider=MockProvider(default_response="not-json"),
        tool_layer=AIToolLayer(),
    )
    try:
        response = await ai_weekly_report_api_context.client.post(
            _url(ai_weekly_report_api_context.project.id),
            headers=ai_weekly_report_api_context.member_headers,
            json={},
        )
    finally:
        app.dependency_overrides[get_ai_assistant_service] = lambda: AIAssistantService(
            provider=MockProvider(
                default_response=json.dumps(_default_report_payload())
            ),
            tool_layer=AIToolLayer(),
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "AI service temporarily unavailable"
