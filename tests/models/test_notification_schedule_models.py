from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from silly_teamwork.db.base import Base
from silly_teamwork.models import (
    Notification,
    NotificationSchedule,
    NotificationScheduleStatus,
    NotificationType,
    Project,
    Task,
    TaskAssignment,
    TaskType,
    Team,
    User,
)


@dataclass(frozen=True, slots=True)
class ScheduleContext:
    creator_id: UUID
    recipient_id: UUID
    collaborative_task_id: UUID
    personal_task_id: UUID
    assignment_id: UUID
    due_at: datetime


@pytest_asyncio.fixture
async def session_factory(
    tmp_path: Path,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'notification-schedules.db'}"
    )

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _create_context(session: AsyncSession) -> ScheduleContext:
    creator = User(username="schedule-creator", password_hash="hash")
    recipient = User(username="schedule-recipient", password_hash="hash")
    session.add_all([creator, recipient])
    await session.flush()

    team = Team(name="Schedule Team", created_by_id=creator.id)
    session.add(team)
    await session.flush()
    project = Project(
        team_id=team.id,
        name="Schedule Project",
        created_by_id=creator.id,
    )
    session.add(project)
    await session.flush()

    due_at = datetime.now(UTC) + timedelta(days=7)
    collaborative_task = Task(
        project_id=project.id,
        title="Collaborative deadline",
        due_at=due_at,
        created_by_id=creator.id,
    )
    personal_task = Task(
        project_id=project.id,
        title="Personal deadline",
        due_at=due_at,
        task_type=TaskType.PERSONAL,
        created_by_id=creator.id,
    )
    session.add_all([collaborative_task, personal_task])
    await session.flush()
    assignment = TaskAssignment(task_id=personal_task.id, user_id=recipient.id)
    session.add(assignment)
    await session.flush()
    return ScheduleContext(
        creator_id=creator.id,
        recipient_id=recipient.id,
        collaborative_task_id=collaborative_task.id,
        personal_task_id=personal_task.id,
        assignment_id=assignment.id,
        due_at=due_at,
    )


def _task_schedule(
    context: ScheduleContext, *, lead_time_minutes: int = 4320
) -> NotificationSchedule:
    return NotificationSchedule(
        user_id=context.recipient_id,
        notification_type=NotificationType.TASK_DUE_SOON,
        task_id=context.collaborative_task_id,
        lead_time_minutes=lead_time_minutes,
        scheduled_for=context.due_at - timedelta(minutes=lead_time_minutes),
        due_at_snapshot=context.due_at,
    )


def _assignment_schedule(
    context: ScheduleContext, *, lead_time_minutes: int = 2880
) -> NotificationSchedule:
    return NotificationSchedule(
        user_id=context.recipient_id,
        notification_type=NotificationType.TASK_DUE_SOON,
        task_assignment_id=context.assignment_id,
        lead_time_minutes=lead_time_minutes,
        scheduled_for=context.due_at - timedelta(minutes=lead_time_minutes),
        due_at_snapshot=context.due_at,
    )


@pytest.mark.asyncio
async def test_notification_schedules_create_with_orm_relationships(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory.begin() as session:
        context = await _create_context(session)
        recipient = await session.get(User, context.recipient_id)
        task = await session.get(Task, context.collaborative_task_id)
        assignment = await session.get(TaskAssignment, context.assignment_id)
        assert recipient is not None and task is not None and assignment is not None
        task_schedule = NotificationSchedule(
            user=recipient,
            task=task,
            notification_type=NotificationType.TASK_DUE_SOON,
            lead_time_minutes=4320,
            scheduled_for=context.due_at - timedelta(minutes=4320),
            due_at_snapshot=context.due_at,
        )
        assignment_schedule = NotificationSchedule(
            user=recipient,
            task_assignment=assignment,
            notification_type=NotificationType.TASK_DUE_SOON,
            lead_time_minutes=2880,
            scheduled_for=context.due_at - timedelta(minutes=2880),
            due_at_snapshot=context.due_at,
        )
        session.add_all([task_schedule, assignment_schedule])
        await session.flush()

        assert task_schedule.status is NotificationScheduleStatus.PENDING
        assert task_schedule.attempt_count == 0
        assert task_schedule.task is not None
        assert task_schedule.user is not None
        assert assignment_schedule.task_assignment is not None
        task_schedule_id = task_schedule.id
        assignment_schedule_id = assignment_schedule.id

    async with session_factory() as session:
        task = await session.scalar(
            select(Task)
            .where(Task.id == context.collaborative_task_id)
            .options(selectinload(Task.notification_schedules))
        )
        assignment = await session.scalar(
            select(TaskAssignment)
            .where(TaskAssignment.id == context.assignment_id)
            .options(selectinload(TaskAssignment.notification_schedules))
        )
        recipient = await session.scalar(
            select(User)
            .where(User.id == context.recipient_id)
            .options(selectinload(User.notification_schedules))
        )
        assert task is not None and assignment is not None and recipient is not None
        assert [schedule.id for schedule in task.notification_schedules] == [task_schedule_id]
        assert [schedule.id for schedule in assignment.notification_schedules] == [
            assignment_schedule_id
        ]
        assert {schedule.id for schedule in recipient.notification_schedules} == {
            task_schedule_id,
            assignment_schedule_id,
        }


@pytest.mark.asyncio
@pytest.mark.parametrize("target_mode", ["missing", "both"])
async def test_notification_schedule_requires_exactly_one_target(
    session_factory: async_sessionmaker[AsyncSession],
    target_mode: str,
) -> None:
    async with session_factory.begin() as session:
        context = await _create_context(session)

    async with session_factory() as session:
        schedule = _task_schedule(context)
        if target_mode == "missing":
            schedule.task_id = None
        else:
            schedule.task_assignment_id = context.assignment_id
        session.add(schedule)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("target_kind", ["task", "assignment"])
async def test_notification_schedule_rejects_duplicate_reminder_node(
    session_factory: async_sessionmaker[AsyncSession],
    target_kind: str,
) -> None:
    async with session_factory.begin() as session:
        context = await _create_context(session)
        factory = _task_schedule if target_kind == "task" else _assignment_schedule
        session.add(factory(context))

    async with session_factory() as session:
        factory = _task_schedule if target_kind == "task" else _assignment_schedule
        session.add(factory(context))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_notification_schedule_status_enum_round_trips(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory.begin() as session:
        context = await _create_context(session)
        schedules = []
        for index, status in enumerate(NotificationScheduleStatus):
            schedule = _task_schedule(context, lead_time_minutes=480 + index)
            schedule.status = status
            schedules.append(schedule)
        session.add_all(schedules)

    async with session_factory() as session:
        loaded = list(
            (
                await session.scalars(
                    select(NotificationSchedule).order_by(
                        NotificationSchedule.lead_time_minutes
                    )
                )
            ).all()
        )
        assert {schedule.status for schedule in loaded} == set(NotificationScheduleStatus)


@pytest.mark.asyncio
async def test_notification_schedule_target_deletes_cascade(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory.begin() as session:
        context = await _create_context(session)
        task_schedule = _task_schedule(context)
        assignment_schedule = _assignment_schedule(context)
        session.add_all([task_schedule, assignment_schedule])
        await session.flush()
        task_schedule_id = task_schedule.id
        assignment_schedule_id = assignment_schedule.id

    async with session_factory.begin() as session:
        task = await session.get(Task, context.collaborative_task_id)
        assignment = await session.get(TaskAssignment, context.assignment_id)
        assert task is not None and assignment is not None
        await session.delete(task)
        await session.delete(assignment)

    async with session_factory() as session:
        assert await session.get(NotificationSchedule, task_schedule_id) is None
        assert await session.get(NotificationSchedule, assignment_schedule_id) is None


@pytest.mark.asyncio
async def test_notification_schedule_recipient_cascades_and_notification_is_preserved(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory.begin() as session:
        context = await _create_context(session)
        notification = Notification(
            user_id=context.recipient_id,
            type=NotificationType.TASK_DUE_SOON,
            title="Scheduled reminder",
            content="Due soon",
            related_task_id=context.collaborative_task_id,
        )
        session.add(notification)
        await session.flush()
        schedule = _task_schedule(context)
        schedule.sent_notification_id = notification.id
        session.add(schedule)
        await session.flush()
        schedule_id = schedule.id
        notification_id = notification.id

    async with session_factory.begin() as session:
        notification = await session.get(Notification, notification_id)
        assert notification is not None
        await session.delete(notification)

    async with session_factory() as session:
        schedule = await session.get(NotificationSchedule, schedule_id)
        assert schedule is not None
        assert schedule.sent_notification_id is None

    async with session_factory.begin() as session:
        recipient = await session.get(User, context.recipient_id)
        assert recipient is not None
        await session.delete(recipient)

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(NotificationSchedule)) == 0
