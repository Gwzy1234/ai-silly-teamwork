from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.enums import NotificationScheduleStatus
from silly_teamwork.models.notification_schedule import NotificationSchedule
from silly_teamwork.models.task_assignment import TaskAssignment

ACTIVE_SCHEDULE_STATUSES = (
    NotificationScheduleStatus.PENDING,
    NotificationScheduleStatus.PROCESSING,
)
CANCELLABLE_SCHEDULE_STATUSES = (
    NotificationScheduleStatus.PENDING,
    NotificationScheduleStatus.FAILED,
)


def due_claim_statement(
    *,
    now: datetime,
    lease_expired_before: datetime,
    max_attempts: int,
    limit: int,
) -> Select[tuple[NotificationSchedule]]:
    return (
        select(NotificationSchedule)
        .where(
            NotificationSchedule.attempt_count < max_attempts,
            or_(
                (
                    (NotificationSchedule.status == NotificationScheduleStatus.PENDING)
                    & (NotificationSchedule.scheduled_for <= now)
                ),
                (
                    (NotificationSchedule.status == NotificationScheduleStatus.FAILED)
                    & (NotificationSchedule.next_attempt_at.is_not(None))
                    & (NotificationSchedule.next_attempt_at <= now)
                ),
                (
                    (NotificationSchedule.status == NotificationScheduleStatus.PROCESSING)
                    & (NotificationSchedule.lease_expires_at.is_not(None))
                    & (NotificationSchedule.lease_expires_at <= lease_expired_before)
                ),
            ),
        )
        .order_by(NotificationSchedule.scheduled_for, NotificationSchedule.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )


async def claim_due(
    session: AsyncSession,
    *,
    now: datetime,
    lease_expires_at: datetime,
    max_attempts: int,
    limit: int,
) -> list[NotificationSchedule]:
    result = await session.execute(
        due_claim_statement(
            now=now,
            lease_expired_before=now,
            max_attempts=max_attempts,
            limit=limit,
        )
    )
    schedules = list(result.scalars().all())
    for schedule in schedules:
        schedule.status = NotificationScheduleStatus.PROCESSING
        schedule.locked_at = now
        schedule.lease_expires_at = lease_expires_at
        schedule.next_attempt_at = None
    await session.flush()
    return schedules


def add(session: AsyncSession, schedule: NotificationSchedule) -> None:
    session.add(schedule)


def add_all(session: AsyncSession, schedules: list[NotificationSchedule]) -> None:
    session.add_all(schedules)


async def list_pending(
    session: AsyncSession,
    *,
    scheduled_before: datetime | None = None,
    limit: int = 100,
) -> list[NotificationSchedule]:
    statement = select(NotificationSchedule).where(
        NotificationSchedule.status == NotificationScheduleStatus.PENDING
    )
    if scheduled_before is not None:
        statement = statement.where(
            NotificationSchedule.scheduled_for <= scheduled_before
        )
    result = await session.execute(
        statement.order_by(
            NotificationSchedule.scheduled_for,
            NotificationSchedule.id,
        ).limit(limit)
    )
    return list(result.scalars().all())


async def list_active_for_task(
    session: AsyncSession, task_id: UUID
) -> list[NotificationSchedule]:
    result = await session.execute(
        select(NotificationSchedule).where(
            NotificationSchedule.task_id == task_id,
            NotificationSchedule.status.in_(ACTIVE_SCHEDULE_STATUSES),
        )
    )
    return list(result.scalars().all())


async def list_active_for_assignment(
    session: AsyncSession, assignment_id: UUID
) -> list[NotificationSchedule]:
    result = await session.execute(
        select(NotificationSchedule).where(
            NotificationSchedule.task_assignment_id == assignment_id,
            NotificationSchedule.status.in_(ACTIVE_SCHEDULE_STATUSES),
        )
    )
    return list(result.scalars().all())


async def get_by_id_for_update(
    session: AsyncSession, schedule_id: UUID
) -> NotificationSchedule | None:
    result = await session.execute(
        select(NotificationSchedule)
        .where(NotificationSchedule.id == schedule_id)
        .with_for_update()
    )
    return result.scalar_one_or_none()


def mark_sent(
    schedule: NotificationSchedule,
    *,
    notification_id: UUID,
    processed_at: datetime,
) -> None:
    schedule.status = NotificationScheduleStatus.SENT
    schedule.sent_notification_id = notification_id
    schedule.processed_at = processed_at
    schedule.locked_at = None
    schedule.lease_expires_at = None
    schedule.next_attempt_at = None
    schedule.last_error = None


def mark_cancelled(
    schedule: NotificationSchedule,
    *,
    cancelled_at: datetime,
) -> None:
    schedule.status = NotificationScheduleStatus.CANCELLED
    schedule.cancelled_at = cancelled_at
    schedule.locked_at = None
    schedule.lease_expires_at = None
    schedule.next_attempt_at = None


def mark_failed(
    schedule: NotificationSchedule,
    *,
    last_error: str,
    next_attempt_at: datetime | None,
) -> None:
    schedule.status = NotificationScheduleStatus.FAILED
    schedule.attempt_count += 1
    schedule.last_error = last_error
    schedule.next_attempt_at = next_attempt_at
    schedule.locked_at = None
    schedule.lease_expires_at = None


async def cancel_pending_for_task(
    session: AsyncSession,
    task_id: UUID,
    *,
    cancelled_at: datetime,
) -> int:
    result = await session.execute(
        update(NotificationSchedule)
        .where(
            NotificationSchedule.task_id == task_id,
            NotificationSchedule.status.in_(CANCELLABLE_SCHEDULE_STATUSES),
        )
        .values(
            status=NotificationScheduleStatus.CANCELLED,
            cancelled_at=cancelled_at,
            next_attempt_at=None,
        )
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def cancel_pending_for_assignment(
    session: AsyncSession,
    assignment_id: UUID,
    *,
    cancelled_at: datetime,
) -> int:
    result = await session.execute(
        update(NotificationSchedule)
        .where(
            NotificationSchedule.task_assignment_id == assignment_id,
            NotificationSchedule.status.in_(CANCELLABLE_SCHEDULE_STATUSES),
        )
        .values(
            status=NotificationScheduleStatus.CANCELLED,
            cancelled_at=cancelled_at,
            next_attempt_at=None,
        )
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def cancel_pending_for_task_assignments(
    session: AsyncSession,
    task_id: UUID,
    *,
    cancelled_at: datetime,
) -> int:
    assignment_ids = select(TaskAssignment.id).where(
        TaskAssignment.task_id == task_id
    )
    result = await session.execute(
        update(NotificationSchedule)
        .where(
            NotificationSchedule.task_assignment_id.in_(assignment_ids),
            NotificationSchedule.status.in_(CANCELLABLE_SCHEDULE_STATUSES),
        )
        .values(
            status=NotificationScheduleStatus.CANCELLED,
            cancelled_at=cancelled_at,
            next_attempt_at=None,
        )
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]
