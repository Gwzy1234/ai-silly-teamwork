from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from silly_teamwork.core.file_storage import LocalFileStorage
from silly_teamwork.db.base import Base
from silly_teamwork.models import (
    AttachmentMode,
    Notification,
    NotificationType,
    Project,
    ProjectMember,
    ProjectRole,
    SystemAdmin,
    SystemAdminRole,
    Team,
    TeamMember,
    TeamRole,
    User,
)
from silly_teamwork.schemas.personal_task import PersonalTaskCreate
from silly_teamwork.schemas.project import ProjectCreate
from silly_teamwork.schemas.task import TaskCreate
from silly_teamwork.services.event_notifications import EventNotificationService
from silly_teamwork.services.files import FileService
from silly_teamwork.services.personal_tasks import PersonalTaskService
from silly_teamwork.services.projects import ProjectService
from silly_teamwork.services.tasks import TaskService


@dataclass(frozen=True, slots=True)
class EventContext:
    session_factory: async_sessionmaker[AsyncSession]
    storage: LocalFileStorage
    leader_id: UUID
    member_id: UUID
    assignee_id: UUID
    unassigned_id: UUID
    super_admin_id: UUID
    team_id: UUID
    project_id: UUID


class MemoryUpload:
    filename = "MRI复习资料.pdf"
    content_type = "application/pdf"

    def __init__(self) -> None:
        self._content = b"event-notification-file"

    async def read(self, _: int = -1) -> bytes:
        content, self._content = self._content, b""
        return content


class FailingEventNotificationService(EventNotificationService):
    async def notify_project_created(
        self,
        session: AsyncSession,
        actor: User,
        project: Project,
    ) -> None:
        raise RuntimeError("event notification failed")


@pytest_asyncio.fixture
async def event_context(tmp_path: Path) -> AsyncIterator[EventContext]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'event-notifications.db'}"
    )

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory.begin() as session:
        leader = User(
            username="event-leader",
            display_name="组长",
            password_hash="hash",
        )
        member = User(username="event-member", password_hash="hash")
        assignee = User(username="event-assignee", password_hash="hash")
        unassigned = User(username="event-unassigned", password_hash="hash")
        super_admin = User(username="event-super-admin", password_hash="hash")
        session.add_all([leader, member, assignee, unassigned, super_admin])
        await session.flush()

        team = Team(name="Event Team", created_by_id=leader.id)
        session.add(team)
        await session.flush()
        session.add_all(
            [
                TeamMember(team_id=team.id, user_id=leader.id, role=TeamRole.OWNER),
                TeamMember(team_id=team.id, user_id=member.id, role=TeamRole.MEMBER),
                TeamMember(team_id=team.id, user_id=assignee.id, role=TeamRole.MEMBER),
                TeamMember(
                    team_id=team.id,
                    user_id=unassigned.id,
                    role=TeamRole.MEMBER,
                ),
            ]
        )
        session.add(
            SystemAdmin(
                user_id=super_admin.id,
                role=SystemAdminRole.SUPER_ADMIN,
            )
        )

        project = Project(
            team_id=team.id,
            name="Existing Subject",
            created_by_id=leader.id,
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
        context = EventContext(
            session_factory=factory,
            storage=LocalFileStorage(tmp_path / "uploads"),
            leader_id=leader.id,
            member_id=member.id,
            assignee_id=assignee.id,
            unassigned_id=unassigned.id,
            super_admin_id=super_admin.id,
            team_id=team.id,
            project_id=project.id,
        )

    yield context
    await engine.dispose()


async def _user(context: EventContext, user_id: UUID) -> User:
    async with context.session_factory() as session:
        user = await session.get(User, user_id)
        assert user is not None
        return user


async def _event_notifications(
    context: EventContext,
    notification_type: NotificationType,
) -> list[Notification]:
    async with context.session_factory() as session:
        result = await session.execute(
            select(Notification)
            .where(Notification.type == notification_type)
            .order_by(Notification.user_id, Notification.id)
        )
        return list(result.scalars().all())


@pytest.mark.asyncio
async def test_project_creation_notifies_team_members_except_creator(
    event_context: EventContext,
) -> None:
    leader = await _user(event_context, event_context.leader_id)
    async with event_context.session_factory() as session:
        project = await ProjectService().create_project(
            session,
            leader,
            event_context.team_id,
            ProjectCreate(name="医学影像设备学"),
        )

    notifications = await _event_notifications(
        event_context, NotificationType.PROJECT_CREATED
    )
    assert {item.user_id for item in notifications} == {
        event_context.member_id,
        event_context.assignee_id,
        event_context.unassigned_id,
    }
    assert all(item.related_project_id == project.id for item in notifications)
    assert all("组长 创建了新科目《医学影像设备学》" == item.content for item in notifications)


@pytest.mark.asyncio
async def test_collaborative_task_creation_notifies_task_member(
    event_context: EventContext,
) -> None:
    leader = await _user(event_context, event_context.leader_id)
    async with event_context.session_factory() as session:
        task = await TaskService().create_task(
            session,
            leader,
            event_context.project_id,
            TaskCreate(
                title="完成第三章PPT",
                owner_user_id=event_context.member_id,
            ),
        )

    notifications = await _event_notifications(
        event_context, NotificationType.TASK_CREATED
    )
    assert len(notifications) == 1
    assert notifications[0].user_id == event_context.member_id
    assert notifications[0].related_task_id == task.id


@pytest.mark.asyncio
async def test_personal_task_creation_notifies_assignments_only(
    event_context: EventContext,
) -> None:
    leader = await _user(event_context, event_context.leader_id)
    async with event_context.session_factory() as session:
        task = await PersonalTaskService().create_personal_task(
            session,
            leader,
            event_context.project_id,
            PersonalTaskCreate(
                title="独立实验报告",
                assignee_user_ids=[event_context.member_id, event_context.assignee_id],
                attachment_mode=AttachmentMode.SHARED,
            ),
        )

    notifications = await _event_notifications(
        event_context, NotificationType.TASK_CREATED
    )
    assert {item.user_id for item in notifications} == {
        event_context.member_id,
        event_context.assignee_id,
    }
    assert all(item.related_task_id == task.id for item in notifications)


@pytest.mark.asyncio
async def test_project_file_notifies_only_team_members_with_project_access(
    event_context: EventContext,
) -> None:
    leader = await _user(event_context, event_context.leader_id)
    service = FileService(storage=event_context.storage)
    async with event_context.session_factory() as session:
        file = await service.upload_project_file(
            session,
            leader,
            event_context.project_id,
            MemoryUpload(),
        )

    notifications = await _event_notifications(
        event_context, NotificationType.FILE_UPLOADED
    )
    assert {item.user_id for item in notifications} == {event_context.member_id}
    assert all(item.related_file_id == file.id for item in notifications)


@pytest.mark.asyncio
async def test_personal_task_file_notifies_assignments_and_admins_without_leaking(
    event_context: EventContext,
) -> None:
    leader = await _user(event_context, event_context.leader_id)
    async with event_context.session_factory() as session:
        task = await PersonalTaskService().create_personal_task(
            session,
            leader,
            event_context.project_id,
            PersonalTaskCreate(
                title="Personal file task",
                assignee_user_ids=[event_context.member_id, event_context.assignee_id],
                attachment_mode=AttachmentMode.SHARED,
            ),
        )

    service = FileService(storage=event_context.storage)
    async with event_context.session_factory() as session:
        file = await service.upload_task_file(
            session,
            leader,
            task.id,
            MemoryUpload(),
        )

    notifications = await _event_notifications(
        event_context, NotificationType.FILE_UPLOADED
    )
    assert {item.user_id for item in notifications} == {
        event_context.member_id,
        event_context.assignee_id,
        event_context.super_admin_id,
    }
    assert event_context.unassigned_id not in {item.user_id for item in notifications}
    assert all(item.related_file_id == file.id for item in notifications)


@pytest.mark.asyncio
async def test_collaborative_task_file_notifies_accessible_task_members(
    event_context: EventContext,
) -> None:
    leader = await _user(event_context, event_context.leader_id)
    async with event_context.session_factory() as session:
        task = await TaskService().create_task(
            session,
            leader,
            event_context.project_id,
            TaskCreate(
                title="Collaborative file task",
                owner_user_id=event_context.member_id,
            ),
        )

    async with event_context.session_factory() as session:
        file = await FileService(storage=event_context.storage).upload_task_file(
            session,
            leader,
            task.id,
            MemoryUpload(),
        )

    notifications = await _event_notifications(
        event_context, NotificationType.FILE_UPLOADED
    )
    assert {item.user_id for item in notifications} == {event_context.member_id}
    assert notifications[0].related_file_id == file.id


@pytest.mark.asyncio
async def test_repeated_event_does_not_create_duplicate_notification(
    event_context: EventContext,
) -> None:
    leader = await _user(event_context, event_context.leader_id)
    async with event_context.session_factory() as session:
        task = await TaskService().create_task(
            session,
            leader,
            event_context.project_id,
            TaskCreate(title="Idempotent event", owner_user_id=event_context.member_id),
        )

    event_service = EventNotificationService()
    async with event_context.session_factory.begin() as session:
        stored_task = await session.get(type(task), task.id)
        actor = await session.get(User, event_context.leader_id)
        assert stored_task is not None and actor is not None
        await event_service.notify_task_created(session, actor, stored_task)
        await event_service.notify_task_created(session, actor, stored_task)

    notifications = await _event_notifications(
        event_context, NotificationType.TASK_CREATED
    )
    assert len(notifications) == 1
    assert notifications[0].user_id == event_context.member_id


@pytest.mark.asyncio
async def test_project_and_notifications_rollback_in_same_transaction(
    event_context: EventContext,
) -> None:
    leader = await _user(event_context, event_context.leader_id)
    service = ProjectService(
        event_notification_service=FailingEventNotificationService()
    )

    async with event_context.session_factory() as session:
        with pytest.raises(RuntimeError, match="event notification failed"):
            await service.create_project(
                session,
                leader,
                event_context.team_id,
                ProjectCreate(name="Rolled back subject"),
            )

    async with event_context.session_factory() as session:
        rolled_back = await session.scalar(
            select(Project).where(Project.name == "Rolled back subject")
        )
        event = await session.scalar(
            select(Notification).where(
                Notification.type == NotificationType.PROJECT_CREATED
            )
        )
        assert rolled_back is None
        assert event is None
