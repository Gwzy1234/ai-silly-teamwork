from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from silly_teamwork.db.base import Base
from silly_teamwork.models import (
    AttachmentMode,
    Notification,
    NotificationSchedule,
    NotificationScheduleStatus,
    NotificationType,
    Project,
    ProjectMember,
    ProjectRole,
    Task,
    TaskAssignment,
    TaskStatus,
    Team,
    TeamMember,
    TeamRole,
    User,
)
from silly_teamwork.schemas.personal_task import PersonalTaskCreate
from silly_teamwork.schemas.task import TaskCreate, TaskUpdate
from silly_teamwork.services.notification_schedules import (
    DEADLINE_LEAD_TIME_MINUTES,
    NotificationScheduleService,
)
from silly_teamwork.services.personal_tasks import PersonalTaskService
from silly_teamwork.services.task_assignments import TaskAssignmentService
from silly_teamwork.services.tasks import TaskService

FIXED_NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class SchedulingContext:
    session_factory: async_sessionmaker[AsyncSession]
    leader_id: UUID
    assignee_ids: tuple[UUID, UUID, UUID]
    project_id: UUID


@pytest_asyncio.fixture
async def scheduling_context(tmp_path: Path) -> AsyncIterator[SchedulingContext]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'notification-schedule-service.db'}"
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
        leader = User(username="schedule-leader", password_hash="hash")
        assignees = [
            User(username=f"schedule-assignee-{index}", password_hash="hash")
            for index in range(3)
        ]
        session.add_all([leader, *assignees])
        await session.flush()
        team = Team(name="Schedule Service Team", created_by_id=leader.id)
        session.add(team)
        await session.flush()
        session.add_all(
            [
                TeamMember(
                    team_id=team.id,
                    user_id=leader.id,
                    role=TeamRole.OWNER,
                ),
                *[
                    TeamMember(
                        team_id=team.id,
                        user_id=user.id,
                        role=TeamRole.MEMBER,
                    )
                    for user in assignees
                ],
            ]
        )
        project = Project(
            team_id=team.id,
            name="Schedule Service Project",
            created_by_id=leader.id,
        )
        session.add(project)
        await session.flush()
        session.add(
            ProjectMember(
                project_id=project.id,
                user_id=leader.id,
                role=ProjectRole.OWNER,
            )
        )
        leader_id = leader.id
        assignee_ids = tuple(user.id for user in assignees)
        project_id = project.id

    yield SchedulingContext(
        session_factory=factory,
        leader_id=leader_id,
        assignee_ids=(assignee_ids[0], assignee_ids[1], assignee_ids[2]),
        project_id=project_id,
    )
    await engine.dispose()


def _schedule_service() -> NotificationScheduleService:
    return NotificationScheduleService(now_provider=lambda: FIXED_NOW)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def _create_collaborative_task(
    context: SchedulingContext,
    *,
    due_at: datetime,
) -> Task:
    service = TaskService(schedule_service=_schedule_service())
    async with context.session_factory() as session:
        leader = await session.get(User, context.leader_id)
        assert leader is not None
        return await service.create_task(
            session,
            leader,
            context.project_id,
            TaskCreate(title="Scheduled collaborative task", due_at=due_at),
        )


async def _create_personal_task(
    context: SchedulingContext,
    *,
    due_at: datetime,
    assignee_ids: tuple[UUID, ...] | None = None,
) -> Task:
    service = PersonalTaskService(schedule_service=_schedule_service())
    async with context.session_factory() as session:
        leader = await session.get(User, context.leader_id)
        assert leader is not None
        return await service.create_personal_task(
            session,
            leader,
            context.project_id,
            PersonalTaskCreate(
                title="Scheduled personal task",
                due_at=due_at,
                assignee_user_ids=list(assignee_ids or context.assignee_ids),
                attachment_mode=AttachmentMode.SHARED,
            ),
        )


async def _schedules_for_task(
    context: SchedulingContext, task_id: UUID
) -> list[NotificationSchedule]:
    async with context.session_factory() as session:
        result = await session.execute(
            select(NotificationSchedule)
            .outerjoin(
                TaskAssignment,
                NotificationSchedule.task_assignment_id == TaskAssignment.id,
            )
            .where(
                (NotificationSchedule.task_id == task_id)
                | (TaskAssignment.task_id == task_id)
            )
            .order_by(
                NotificationSchedule.created_at,
                NotificationSchedule.lead_time_minutes.desc(),
            )
        )
        return list(result.scalars().all())


@pytest.mark.asyncio
async def test_collaborative_task_creation_generates_five_deadline_schedules(
    scheduling_context: SchedulingContext,
) -> None:
    due_at = FIXED_NOW + timedelta(days=7)
    task = await _create_collaborative_task(scheduling_context, due_at=due_at)
    schedules = await _schedules_for_task(scheduling_context, task.id)

    assert len(schedules) == 5
    assert {item.lead_time_minutes for item in schedules} == set(
        DEADLINE_LEAD_TIME_MINUTES
    )
    assert all(item.task_id == task.id for item in schedules)
    assert all(item.user_id == scheduling_context.leader_id for item in schedules)
    assert all(item.status is NotificationScheduleStatus.PENDING for item in schedules)
    assert all(
        _as_utc(item.scheduled_for)
        == due_at - timedelta(minutes=item.lead_time_minutes)
        for item in schedules
    )


@pytest.mark.asyncio
async def test_personal_task_creation_generates_five_schedules_per_assignment(
    scheduling_context: SchedulingContext,
) -> None:
    due_at = FIXED_NOW + timedelta(days=7)
    task = await _create_personal_task(scheduling_context, due_at=due_at)
    schedules = await _schedules_for_task(scheduling_context, task.id)

    assert len(schedules) == 15
    assert {item.user_id for item in schedules} == set(scheduling_context.assignee_ids)
    assert all(item.task_id is None for item in schedules)
    assert all(item.task_assignment_id is not None for item in schedules)
    assert all(_as_utc(item.due_at_snapshot) == due_at for item in schedules)


@pytest.mark.asyncio
async def test_assignment_completion_cancels_and_reopen_recreates_future_schedules(
    scheduling_context: SchedulingContext,
) -> None:
    due_at = FIXED_NOW + timedelta(days=7)
    task = await _create_personal_task(
        scheduling_context,
        due_at=due_at,
        assignee_ids=(scheduling_context.assignee_ids[0],),
    )
    async with scheduling_context.session_factory() as session:
        assignment = await session.scalar(
            select(TaskAssignment).where(TaskAssignment.task_id == task.id)
        )
        assignee = await session.get(User, scheduling_context.assignee_ids[0])
        assert assignment is not None and assignee is not None
        assignment_id = assignment.id

    service = TaskAssignmentService(schedule_service=_schedule_service())
    async with scheduling_context.session_factory() as session:
        assignee = await session.get(User, scheduling_context.assignee_ids[0])
        assert assignee is not None
        await service.change_status(
            session, assignee, assignment_id, TaskStatus.IN_PROGRESS
        )
        await service.change_status(session, assignee, assignment_id, TaskStatus.DONE)

    schedules = await _schedules_for_task(scheduling_context, task.id)
    assert len(schedules) == 5
    assert all(item.status is NotificationScheduleStatus.CANCELLED for item in schedules)
    assert all(
        item.cancelled_at is not None and _as_utc(item.cancelled_at) == FIXED_NOW
        for item in schedules
    )

    async with scheduling_context.session_factory() as session:
        assignee = await session.get(User, scheduling_context.assignee_ids[0])
        assert assignee is not None
        await service.change_status(
            session, assignee, assignment_id, TaskStatus.IN_PROGRESS
        )

    schedules = await _schedules_for_task(scheduling_context, task.id)
    assert len(schedules) == 10
    assert sum(
        item.status is NotificationScheduleStatus.CANCELLED for item in schedules
    ) == 5
    assert sum(item.status is NotificationScheduleStatus.PENDING for item in schedules) == 5


@pytest.mark.asyncio
async def test_collaborative_due_date_change_cancels_old_and_creates_new_schedules(
    scheduling_context: SchedulingContext,
) -> None:
    original_due_at = FIXED_NOW + timedelta(days=7)
    new_due_at = FIXED_NOW + timedelta(days=10)
    task = await _create_collaborative_task(
        scheduling_context, due_at=original_due_at
    )
    service = TaskService(schedule_service=_schedule_service())
    async with scheduling_context.session_factory() as session:
        leader = await session.get(User, scheduling_context.leader_id)
        assert leader is not None
        await service.update_task(
            session,
            leader,
            task.id,
            TaskUpdate(due_at=new_due_at),
        )

    schedules = await _schedules_for_task(scheduling_context, task.id)
    assert len(schedules) == 10
    old = [
        item for item in schedules if _as_utc(item.due_at_snapshot) == original_due_at
    ]
    new = [item for item in schedules if _as_utc(item.due_at_snapshot) == new_due_at]
    assert len(old) == 5 and len(new) == 5
    assert all(item.status is NotificationScheduleStatus.CANCELLED for item in old)
    assert all(item.status is NotificationScheduleStatus.PENDING for item in new)


@pytest.mark.asyncio
async def test_personal_due_date_rebuild_preserves_history_for_all_assignments(
    scheduling_context: SchedulingContext,
) -> None:
    original_due_at = FIXED_NOW + timedelta(days=7)
    new_due_at = FIXED_NOW + timedelta(days=9)
    task = await _create_personal_task(
        scheduling_context,
        due_at=original_due_at,
    )
    service = _schedule_service()
    async with scheduling_context.session_factory.begin() as session:
        loaded_task = await session.get(Task, task.id)
        assert loaded_task is not None
        loaded_task.due_at = new_due_at
        await service.rebuild_task_deadline_schedules(session, loaded_task)

    schedules = await _schedules_for_task(scheduling_context, task.id)
    assert len(schedules) == 30
    assert sum(
        item.status is NotificationScheduleStatus.CANCELLED for item in schedules
    ) == 15
    assert sum(item.status is NotificationScheduleStatus.PENDING for item in schedules) == 15
    assert sum(_as_utc(item.due_at_snapshot) == new_due_at for item in schedules) == 15


@pytest.mark.asyncio
async def test_schedule_creation_is_idempotent_and_does_not_add_notifications(
    scheduling_context: SchedulingContext,
) -> None:
    due_at = FIXED_NOW + timedelta(days=7)
    task = await _create_collaborative_task(scheduling_context, due_at=due_at)
    service = _schedule_service()
    async with scheduling_context.session_factory.begin() as session:
        loaded_task = await session.get(Task, task.id)
        assert loaded_task is not None
        assert await service.create_task_deadline_schedules(session, loaded_task) == []
        assert await service.create_task_deadline_schedules(session, loaded_task) == []

    async with scheduling_context.session_factory() as session:
        schedule_count = await session.scalar(
            select(func.count()).select_from(NotificationSchedule)
        )
        notification_count = await session.scalar(
            select(func.count()).select_from(Notification)
        )
        assert schedule_count == 5
        assert notification_count == 1
        event = await session.scalar(select(Notification))
        assert event is not None
        assert event.type is NotificationType.TASK_CREATED


@pytest.mark.asyncio
async def test_only_future_schedule_nodes_are_generated(
    scheduling_context: SchedulingContext,
) -> None:
    due_at = FIXED_NOW + timedelta(hours=10)
    task = await _create_collaborative_task(scheduling_context, due_at=due_at)
    schedules = await _schedules_for_task(scheduling_context, task.id)

    assert [item.lead_time_minutes for item in schedules] == [480]
    assert _as_utc(schedules[0].scheduled_for) == FIXED_NOW + timedelta(hours=2)
