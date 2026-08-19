from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from silly_teamwork.core.security import create_access_token, hash_password
from silly_teamwork.db.base import Base
from silly_teamwork.db.session import get_db_session
from silly_teamwork.main import app
from silly_teamwork.models import (
    Notification,
    NotificationType,
    Project,
    ProjectMember,
    ProjectRole,
    Task,
    TaskMember,
    TaskRole,
    TaskStatus,
    Team,
    TeamMember,
    TeamRole,
    User,
)
from silly_teamwork.services.deadlines import DeadlineService
from silly_teamwork.services.exceptions import TaskNotFoundError
from silly_teamwork.services.notifications import NotificationService

pytestmark = pytest.mark.asyncio


@dataclass(frozen=True, slots=True)
class DeadlineNotificationContext:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]
    user: User
    other_user: User
    accessible_task: Task
    overdue_task: Task
    inaccessible_task: Task
    own_notification: Notification
    other_notification: Notification
    headers: dict[str, str]


@pytest_asyncio.fixture
async def deadline_notification_context() -> AsyncIterator[DeadlineNotificationContext]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    now = datetime.now(UTC)
    async with factory.begin() as session:
        user = User(username="deadline_user", password_hash=hash_password("password"))
        other_user = User(username="deadline_other", password_hash=hash_password("password"))
        session.add_all([user, other_user])
        await session.flush()

        team = Team(name="Deadline Team", created_by_id=user.id)
        hidden_team = Team(name="Hidden Team", created_by_id=other_user.id)
        session.add_all([team, hidden_team])
        await session.flush()
        session.add_all(
            [
                TeamMember(team_id=team.id, user_id=user.id, role=TeamRole.OWNER),
                TeamMember(
                    team_id=hidden_team.id,
                    user_id=other_user.id,
                    role=TeamRole.OWNER,
                ),
            ]
        )

        project = Project(team_id=team.id, name="Visible Project", created_by_id=user.id)
        hidden_project = Project(
            team_id=hidden_team.id,
            name="Hidden Project",
            created_by_id=other_user.id,
        )
        session.add_all([project, hidden_project])
        await session.flush()
        session.add_all(
            [
                ProjectMember(
                    project_id=project.id,
                    user_id=user.id,
                    role=ProjectRole.OWNER,
                ),
                ProjectMember(
                    project_id=hidden_project.id,
                    user_id=other_user.id,
                    role=ProjectRole.OWNER,
                ),
            ]
        )

        accessible_task = Task(
            project_id=project.id,
            title="Due soon",
            due_at=now + timedelta(hours=2),
            created_by_id=user.id,
        )
        overdue_task = Task(
            project_id=project.id,
            title="Already overdue",
            due_at=now - timedelta(hours=2),
            created_by_id=user.id,
        )
        inaccessible_task = Task(
            project_id=hidden_project.id,
            title="Hidden due soon",
            due_at=now + timedelta(hours=1),
            created_by_id=other_user.id,
        )
        completed_task = Task(
            project_id=project.id,
            title="Completed task",
            status=TaskStatus.DONE,
            due_at=now - timedelta(days=1),
            completed_at=now,
            created_by_id=user.id,
        )
        session.add_all(
            [accessible_task, overdue_task, inaccessible_task, completed_task]
        )
        await session.flush()
        session.add_all(
            [
                TaskMember(
                    task_id=accessible_task.id,
                    user_id=user.id,
                    role=TaskRole.OWNER,
                ),
                TaskMember(
                    task_id=overdue_task.id,
                    user_id=user.id,
                    role=TaskRole.OWNER,
                ),
                TaskMember(
                    task_id=inaccessible_task.id,
                    user_id=other_user.id,
                    role=TaskRole.OWNER,
                ),
                TaskMember(
                    task_id=completed_task.id,
                    user_id=user.id,
                    role=TaskRole.OWNER,
                ),
            ]
        )

        own_notification = Notification(
            user_id=user.id,
            type=NotificationType.TASK_DUE_SOON,
            title="Task due soon",
            content="Due within two hours",
            related_task_id=accessible_task.id,
        )
        other_notification = Notification(
            user_id=other_user.id,
            type=NotificationType.SYSTEM,
            title="Other user's notification",
            content="Private",
        )
        session.add_all([own_notification, other_notification])
        await session.flush()

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield DeadlineNotificationContext(
            client=client,
            session_factory=factory,
            user=user,
            other_user=other_user,
            accessible_task=accessible_task,
            overdue_task=overdue_task,
            inaccessible_task=inaccessible_task,
            own_notification=own_notification,
            other_notification=other_notification,
            headers=_headers(user.id),
        )

    app.dependency_overrides.clear()
    await engine.dispose()


def _headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def test_user_only_lists_own_notifications(
    deadline_notification_context: DeadlineNotificationContext,
) -> None:
    context = deadline_notification_context
    response = await context.client.get("/api/v1/notifications", headers=context.headers)

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(context.own_notification.id)]


async def test_inaccessible_task_cannot_generate_notification(
    deadline_notification_context: DeadlineNotificationContext,
) -> None:
    context = deadline_notification_context
    async with context.session_factory() as session:
        with pytest.raises(TaskNotFoundError):
            await NotificationService().create_notification(
                session,
                context.user.id,
                NotificationType.TASK_DUE_SOON,
                "Hidden task",
                "Must not leak",
                related_task_id=context.inaccessible_task.id,
            )


async def test_mark_notification_as_read_and_reject_other_users_notification(
    deadline_notification_context: DeadlineNotificationContext,
) -> None:
    context = deadline_notification_context
    response = await context.client.patch(
        f"/api/v1/notifications/{context.own_notification.id}/read",
        headers=context.headers,
    )
    assert response.status_code == 200
    assert response.json()["is_read"] is True
    assert response.json()["read_at"] is not None

    hidden = await context.client.patch(
        f"/api/v1/notifications/{context.other_notification.id}/read",
        headers=context.headers,
    )
    assert hidden.status_code == 404


async def test_mark_all_as_read_only_updates_current_user(
    deadline_notification_context: DeadlineNotificationContext,
) -> None:
    context = deadline_notification_context
    response = await context.client.patch(
        "/api/v1/notifications/read-all", headers=context.headers
    )
    assert response.status_code == 200
    assert response.json() == {"updated_count": 1}

    async with context.session_factory() as session:
        own = await session.get(Notification, context.own_notification.id)
        other = await session.get(Notification, context.other_notification.id)
        assert own is not None and own.is_read and own.read_at is not None
        assert other is not None and not other.is_read and other.read_at is None


async def test_upcoming_and_overdue_tasks_respect_access_and_status(
    deadline_notification_context: DeadlineNotificationContext,
) -> None:
    context = deadline_notification_context
    upcoming = await context.client.get(
        "/api/v1/tasks/upcoming?hours=4", headers=context.headers
    )
    overdue = await context.client.get("/api/v1/tasks/overdue", headers=context.headers)

    assert upcoming.status_code == 200
    assert [item["id"] for item in upcoming.json()] == [str(context.accessible_task.id)]
    assert overdue.status_code == 200
    assert [item["id"] for item in overdue.json()] == [str(context.overdue_task.id)]


async def test_deadline_check_notifies_owners_and_deduplicates_unread(
    deadline_notification_context: DeadlineNotificationContext,
) -> None:
    context = deadline_notification_context
    async with context.session_factory() as session:
        service = DeadlineService()
        await service.create_task_deadline_notifications(session, due_soon_hours=4)
        await service.create_task_deadline_notifications(session, due_soon_hours=4)

    async with context.session_factory() as session:
        result = await session.execute(
            select(Notification).where(
                Notification.user_id == context.user.id,
                Notification.related_task_id.in_(
                    [context.accessible_task.id, context.overdue_task.id]
                ),
            )
        )
        reminders = list(result.scalars().all())
        assert len(reminders) == 2
        assert {(item.related_task_id, item.type) for item in reminders} == {
            (context.accessible_task.id, NotificationType.TASK_DUE_SOON),
            (context.overdue_task.id, NotificationType.TASK_OVERDUE),
        }


async def test_deadline_check_does_not_notify_non_owners_or_completed_tasks(
    deadline_notification_context: DeadlineNotificationContext,
) -> None:
    context = deadline_notification_context
    async with context.session_factory() as session:
        await DeadlineService().create_task_deadline_notifications(
            session, due_soon_hours=4
        )

    async with context.session_factory() as session:
        result = await session.execute(select(Notification))
        reminders = [
            item
            for item in result.scalars().all()
            if item.type in {
                NotificationType.TASK_DUE_SOON,
                NotificationType.TASK_OVERDUE,
            }
        ]
        assert all(
            item.user_id
            == (
                context.other_user.id
                if item.related_task_id == context.inaccessible_task.id
                else context.user.id
            )
            for item in reminders
        )
        assert {item.related_task_id for item in reminders} == {
            context.accessible_task.id,
            context.overdue_task.id,
            context.inaccessible_task.id,
        }


@pytest.mark.parametrize(
    ("status", "due_delta"),
    [
        (TaskStatus.DONE, timedelta(hours=1)),
        (TaskStatus.CANCELLED, timedelta(hours=1)),
        (TaskStatus.CANCELLED, timedelta(hours=-1)),
    ],
)
async def test_deadline_check_ignores_non_remindable_task_statuses(
    deadline_notification_context: DeadlineNotificationContext,
    status: TaskStatus,
    due_delta: timedelta,
) -> None:
    context = deadline_notification_context
    async with context.session_factory() as session:
        task = Task(
            project_id=context.accessible_task.project_id,
            title=f"Ignored {status.value} task",
            status=status,
            due_at=datetime.now(UTC) + due_delta,
            completed_at=datetime.now(UTC) if status is TaskStatus.DONE else None,
            created_by_id=context.user.id,
        )
        session.add(task)
        await session.flush()
        session.add(
            TaskMember(task_id=task.id, user_id=context.user.id, role=TaskRole.OWNER)
        )
        await session.commit()
        task_id = task.id

    async with context.session_factory() as session:
        await DeadlineService().create_task_deadline_notifications(
            session, due_soon_hours=4
        )

    async with context.session_factory() as session:
        result = await session.execute(
            select(Notification).where(Notification.related_task_id == task_id)
        )
        assert result.scalars().all() == []


async def test_deadline_and_notification_endpoints_require_jwt(
    deadline_notification_context: DeadlineNotificationContext,
) -> None:
    context = deadline_notification_context
    for path in (
        "/api/v1/notifications",
        f"/api/v1/notifications/{context.own_notification.id}/read",
        "/api/v1/notifications/read-all",
        "/api/v1/tasks/upcoming",
        "/api/v1/tasks/overdue",
    ):
        method = "PATCH" if "/read" in path else "GET"
        response = await context.client.request(method, path)
        assert response.status_code == 401


async def test_openapi_documents_deadline_and_notification_operations() -> None:
    schema = app.openapi()
    expected_operations = {
        ("get", "/api/v1/notifications"),
        ("patch", "/api/v1/notifications/{notification_id}/read"),
        ("patch", "/api/v1/notifications/read-all"),
        ("get", "/api/v1/tasks/upcoming"),
        ("get", "/api/v1/tasks/overdue"),
    }
    for method, path in expected_operations:
        assert schema["paths"][path][method]["security"] == [{"HTTPBearer": []}]
