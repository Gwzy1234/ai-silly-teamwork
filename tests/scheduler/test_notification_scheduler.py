from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import event, func, select
from sqlalchemy.dialects import postgresql
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
    TaskMember,
    TaskRole,
    TaskStatus,
    TaskType,
    Team,
    TeamMember,
    TeamRole,
    User,
)
from silly_teamwork.repositories.notification_schedules import due_claim_statement
from silly_teamwork.scheduler.service import NotificationScheduler
from silly_teamwork.services.notifications import NotificationService

FIXED_NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class SchedulerContext:
    session_factory: async_sessionmaker[AsyncSession]
    owner_id: UUID
    assignee_id: UUID
    collaborative_task_id: UUID
    personal_task_id: UUID
    assignment_id: UUID


@dataclass(slots=True)
class MutableClock:
    current: datetime

    def __call__(self) -> datetime:
        return self.current


class FailingNotificationService(NotificationService):
    async def create_notification(
        self,
        session: AsyncSession,
        user_id: UUID,
        notification_type: NotificationType,
        title: str,
        content: str,
        *,
        related_task_id: UUID | None = None,
        related_project_id: UUID | None = None,
        commit: bool = True,
        deduplicate: bool = True,
    ) -> Notification:
        raise RuntimeError("temporary notification failure")


@pytest_asyncio.fixture
async def scheduler_context(tmp_path: Path) -> AsyncIterator[SchedulerContext]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'notification-scheduler.db'}"
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
        owner = User(username="scheduler-owner", password_hash="hash")
        assignee = User(username="scheduler-assignee", password_hash="hash")
        session.add_all([owner, assignee])
        await session.flush()

        team = Team(name="Scheduler Team", created_by_id=owner.id)
        session.add(team)
        await session.flush()
        session.add_all(
            [
                TeamMember(team_id=team.id, user_id=owner.id, role=TeamRole.OWNER),
                TeamMember(
                    team_id=team.id,
                    user_id=assignee.id,
                    role=TeamRole.MEMBER,
                ),
            ]
        )

        project = Project(
            team_id=team.id,
            name="Scheduler Subject",
            created_by_id=owner.id,
        )
        session.add(project)
        await session.flush()
        session.add(
            ProjectMember(
                project_id=project.id,
                user_id=owner.id,
                role=ProjectRole.OWNER,
            )
        )

        collaborative_task = Task(
            project_id=project.id,
            created_by_id=owner.id,
            title="Collaborative report",
            task_type=TaskType.COLLABORATIVE,
            attachment_mode=AttachmentMode.SHARED,
            due_at=FIXED_NOW + timedelta(hours=24),
        )
        personal_task = Task(
            project_id=project.id,
            created_by_id=owner.id,
            title="Personal report",
            task_type=TaskType.PERSONAL,
            attachment_mode=AttachmentMode.SHARED,
            due_at=FIXED_NOW + timedelta(hours=24),
        )
        session.add_all([collaborative_task, personal_task])
        await session.flush()
        task_member = TaskMember(
            task_id=collaborative_task.id,
            user_id=owner.id,
            role=TaskRole.OWNER,
        )
        assignment = TaskAssignment(
            task_id=personal_task.id,
            user_id=assignee.id,
            status=TaskStatus.TODO,
        )
        session.add_all([task_member, assignment])
        await session.flush()

        context = SchedulerContext(
            session_factory=factory,
            owner_id=owner.id,
            assignee_id=assignee.id,
            collaborative_task_id=collaborative_task.id,
            personal_task_id=personal_task.id,
            assignment_id=assignment.id,
        )

    yield context
    await engine.dispose()


async def _add_collaborative_schedule(
    context: SchedulerContext,
) -> NotificationSchedule:
    async with context.session_factory.begin() as session:
        schedule = NotificationSchedule(
            user_id=context.owner_id,
            notification_type=NotificationType.TASK_DUE_SOON,
            task_id=context.collaborative_task_id,
            lead_time_minutes=1440,
            scheduled_for=FIXED_NOW,
            due_at_snapshot=FIXED_NOW + timedelta(hours=24),
        )
        session.add(schedule)
        await session.flush()
        return schedule


async def _add_assignment_schedule(context: SchedulerContext) -> NotificationSchedule:
    async with context.session_factory.begin() as session:
        schedule = NotificationSchedule(
            user_id=context.assignee_id,
            notification_type=NotificationType.TASK_DUE_SOON,
            task_assignment_id=context.assignment_id,
            lead_time_minutes=1440,
            scheduled_for=FIXED_NOW,
            due_at_snapshot=FIXED_NOW + timedelta(hours=24),
        )
        session.add(schedule)
        await session.flush()
        return schedule


async def _notification_count(context: SchedulerContext) -> int:
    async with context.session_factory() as session:
        return int(await session.scalar(select(func.count(Notification.id))) or 0)


@pytest.mark.asyncio
async def test_due_schedule_creates_notification_and_marks_schedule_sent(
    scheduler_context: SchedulerContext,
) -> None:
    schedule = await _add_collaborative_schedule(scheduler_context)
    scheduler = NotificationScheduler(
        scheduler_context.session_factory,
        now_provider=lambda: FIXED_NOW,
    )

    result = await scheduler.run_once()

    assert result.claimed == 1
    assert result.sent == 1
    assert result.failed == 0
    async with scheduler_context.session_factory() as session:
        stored = await session.get(NotificationSchedule, schedule.id)
        assert stored is not None
        assert stored.status is NotificationScheduleStatus.SENT
        assert stored.sent_notification_id is not None
        notification = await session.get(Notification, stored.sent_notification_id)
        assert notification is not None
        assert notification.user_id == scheduler_context.owner_id
        assert notification.related_task_id == scheduler_context.collaborative_task_id
        assert "24小时后截止" in notification.content


@pytest.mark.asyncio
async def test_repeated_scheduler_runs_and_two_instances_are_idempotent(
    scheduler_context: SchedulerContext,
) -> None:
    await _add_collaborative_schedule(scheduler_context)
    first = NotificationScheduler(
        scheduler_context.session_factory,
        now_provider=lambda: FIXED_NOW,
    )
    second = NotificationScheduler(
        scheduler_context.session_factory,
        now_provider=lambda: FIXED_NOW,
    )

    first_result = await first.run_once()
    second_result = await second.run_once()
    repeated_result = await first.run_once()

    assert first_result.sent == 1
    assert second_result.claimed == 0
    assert repeated_result.claimed == 0
    assert await _notification_count(scheduler_context) == 1


def test_claim_query_uses_postgresql_skip_locked() -> None:
    statement = due_claim_statement(
        now=FIXED_NOW,
        lease_expired_before=FIXED_NOW,
        max_attempts=5,
        limit=100,
    )

    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE SKIP LOCKED" in sql


def test_retry_backoff_uses_one_five_fifteen_and_thirty_minutes(
    scheduler_context: SchedulerContext,
) -> None:
    scheduler = NotificationScheduler(
        scheduler_context.session_factory,
        now_provider=lambda: FIXED_NOW,
    )

    assert scheduler._next_attempt_at(FIXED_NOW, 1) == FIXED_NOW + timedelta(minutes=1)
    assert scheduler._next_attempt_at(FIXED_NOW, 2) == FIXED_NOW + timedelta(minutes=5)
    assert scheduler._next_attempt_at(FIXED_NOW, 3) == FIXED_NOW + timedelta(minutes=15)
    assert scheduler._next_attempt_at(FIXED_NOW, 4) == FIXED_NOW + timedelta(minutes=30)
    assert scheduler._next_attempt_at(FIXED_NOW, 5) is None


@pytest.mark.asyncio
async def test_completed_collaborative_task_cancels_schedule(
    scheduler_context: SchedulerContext,
) -> None:
    schedule = await _add_collaborative_schedule(scheduler_context)
    async with scheduler_context.session_factory.begin() as session:
        task = await session.get(Task, scheduler_context.collaborative_task_id)
        assert task is not None
        task.status = TaskStatus.DONE

    result = await NotificationScheduler(
        scheduler_context.session_factory,
        now_provider=lambda: FIXED_NOW,
    ).run_once()

    assert result.cancelled == 1
    assert await _notification_count(scheduler_context) == 0
    async with scheduler_context.session_factory() as session:
        stored = await session.get(NotificationSchedule, schedule.id)
        assert stored is not None
        assert stored.status is NotificationScheduleStatus.CANCELLED


@pytest.mark.asyncio
async def test_completed_personal_assignment_cancels_schedule(
    scheduler_context: SchedulerContext,
) -> None:
    schedule = await _add_assignment_schedule(scheduler_context)
    async with scheduler_context.session_factory.begin() as session:
        assignment = await session.get(TaskAssignment, scheduler_context.assignment_id)
        assert assignment is not None
        assignment.status = TaskStatus.DONE

    result = await NotificationScheduler(
        scheduler_context.session_factory,
        now_provider=lambda: FIXED_NOW,
    ).run_once()

    assert result.cancelled == 1
    assert await _notification_count(scheduler_context) == 0
    async with scheduler_context.session_factory() as session:
        stored = await session.get(NotificationSchedule, schedule.id)
        assert stored is not None
        assert stored.status is NotificationScheduleStatus.CANCELLED


@pytest.mark.asyncio
async def test_due_date_snapshot_mismatch_cancels_schedule(
    scheduler_context: SchedulerContext,
) -> None:
    schedule = await _add_collaborative_schedule(scheduler_context)
    async with scheduler_context.session_factory.begin() as session:
        task = await session.get(Task, scheduler_context.collaborative_task_id)
        assert task is not None
        task.due_at = FIXED_NOW + timedelta(hours=25)

    result = await NotificationScheduler(
        scheduler_context.session_factory,
        now_provider=lambda: FIXED_NOW,
    ).run_once()

    assert result.cancelled == 1
    assert await _notification_count(scheduler_context) == 0
    async with scheduler_context.session_factory() as session:
        stored = await session.get(NotificationSchedule, schedule.id)
        assert stored is not None
        assert stored.status is NotificationScheduleStatus.CANCELLED


@pytest.mark.asyncio
async def test_failure_records_retry_and_later_retry_succeeds(
    scheduler_context: SchedulerContext,
) -> None:
    schedule = await _add_collaborative_schedule(scheduler_context)
    clock = MutableClock(FIXED_NOW)
    failing_scheduler = NotificationScheduler(
        scheduler_context.session_factory,
        notification_service=FailingNotificationService(),
        now_provider=clock,
    )

    failed_result = await failing_scheduler.run_once()

    assert failed_result.failed == 1
    async with scheduler_context.session_factory() as session:
        failed = await session.get(NotificationSchedule, schedule.id)
        assert failed is not None
        assert failed.status is NotificationScheduleStatus.FAILED
        assert failed.attempt_count == 1
        assert failed.next_attempt_at is not None
        assert failed.last_error == "temporary notification failure"

    clock.current = FIXED_NOW + timedelta(seconds=59)
    assert (await failing_scheduler.run_once()).claimed == 0

    clock.current = FIXED_NOW + timedelta(seconds=60)
    retry_result = await NotificationScheduler(
        scheduler_context.session_factory,
        now_provider=clock,
    ).run_once()

    assert retry_result.sent == 1
    assert await _notification_count(scheduler_context) == 1
    async with scheduler_context.session_factory() as session:
        sent = await session.get(NotificationSchedule, schedule.id)
        assert sent is not None
        assert sent.status is NotificationScheduleStatus.SENT
        assert sent.attempt_count == 1
        assert sent.sent_notification_id is not None
