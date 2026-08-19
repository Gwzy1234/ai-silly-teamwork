from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from silly_teamwork.models.enums import (
    NotificationScheduleStatus,
    TaskType,
)
from silly_teamwork.models.notification_schedule import NotificationSchedule
from silly_teamwork.models.task import Task
from silly_teamwork.repositories import (
    notification_schedules,
    notifications,
    task_assignments,
    task_members,
    tasks,
)
from silly_teamwork.services.notification_schedules import REMINDABLE_STATUSES
from silly_teamwork.services.notifications import NotificationService

logger = logging.getLogger(__name__)

RETRY_DELAYS_SECONDS = (60, 300, 900, 1800)
MAX_ATTEMPTS = len(RETRY_DELAYS_SECONDS) + 1
Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class SchedulerRunResult:
    claimed: int = 0
    sent: int = 0
    cancelled: int = 0
    failed: int = 0


class NotificationScheduler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notification_service: NotificationService | None = None,
        now_provider: Clock | None = None,
        batch_size: int = 100,
        lease_seconds: int = 300,
        max_attempts: int = MAX_ATTEMPTS,
    ) -> None:
        self.session_factory = session_factory
        self.notifications = notification_service or NotificationService()
        self._now = now_provider or (lambda: datetime.now(UTC))
        self.batch_size = batch_size
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts

    async def run_once(self) -> SchedulerRunResult:
        claimed_ids = await self._claim_due()
        sent = 0
        cancelled = 0
        failed = 0
        for schedule_id in claimed_ids:
            try:
                outcome = await self._process_claimed(schedule_id)
            except Exception as error:
                logger.exception("Notification schedule processing failed")
                await self._record_failure(schedule_id, error)
                failed += 1
                continue
            if outcome is NotificationScheduleStatus.SENT:
                sent += 1
            elif outcome is NotificationScheduleStatus.CANCELLED:
                cancelled += 1
        return SchedulerRunResult(
            claimed=len(claimed_ids),
            sent=sent,
            cancelled=cancelled,
            failed=failed,
        )

    async def _claim_due(self) -> list[UUID]:
        now = self._utc(self._now())
        lease_expires_at = now + timedelta(seconds=self.lease_seconds)
        async with self.session_factory.begin() as session:
            schedules = await notification_schedules.claim_due(
                session,
                now=now,
                lease_expires_at=lease_expires_at,
                max_attempts=self.max_attempts,
                limit=self.batch_size,
            )
            return [schedule.id for schedule in schedules]

    async def _process_claimed(
        self, schedule_id: UUID
    ) -> NotificationScheduleStatus | None:
        now = self._utc(self._now())
        async with self.session_factory.begin() as session:
            schedule = await notification_schedules.get_by_id_for_update(
                session, schedule_id
            )
            if schedule is None or schedule.status is not NotificationScheduleStatus.PROCESSING:
                return None
            if schedule.sent_notification_id is not None:
                notification = await notifications.get_by_id(
                    session, schedule.sent_notification_id
                )
                if notification is not None:
                    notification_schedules.mark_sent(
                        schedule,
                        notification_id=notification.id,
                        processed_at=now,
                    )
                    return NotificationScheduleStatus.SENT

            task = await self._validate_and_get_task(session, schedule)
            if task is None:
                notification_schedules.mark_cancelled(schedule, cancelled_at=now)
                return NotificationScheduleStatus.CANCELLED

            notification = await self.notifications.create_notification(
                session,
                schedule.user_id,
                schedule.notification_type,
                "任务即将到期",
                self._content(task, schedule),
                related_task_id=task.id,
                commit=False,
                deduplicate=False,
            )
            notification_schedules.mark_sent(
                schedule,
                notification_id=notification.id,
                processed_at=now,
            )
            await session.flush()
            return NotificationScheduleStatus.SENT

    async def _validate_and_get_task(
        self,
        session: AsyncSession,
        schedule: NotificationSchedule,
    ) -> Task | None:
        if schedule.task_id is not None:
            task = await tasks.get_by_id(session, schedule.task_id)
            if (
                task is None
                or task.task_type is not TaskType.COLLABORATIVE
                or task.status not in REMINDABLE_STATUSES
            ):
                return None
            owner = await task_members.get_owner(session, task.id)
            if owner is None or owner.user_id != schedule.user_id:
                return None
        elif schedule.task_assignment_id is not None:
            assignment = await task_assignments.get_by_id(
                session, schedule.task_assignment_id
            )
            if (
                assignment is None
                or assignment.status not in REMINDABLE_STATUSES
                or assignment.user_id != schedule.user_id
            ):
                return None
            task = await tasks.get_by_id(session, assignment.task_id)
            if task is None or task.task_type is not TaskType.PERSONAL:
                return None
        else:
            return None

        if task.due_at is None:
            return None
        if self._utc(task.due_at) != self._utc(schedule.due_at_snapshot):
            return None
        return task

    async def _record_failure(self, schedule_id: UUID, error: Exception) -> None:
        now = self._utc(self._now())
        async with self.session_factory.begin() as session:
            schedule = await notification_schedules.get_by_id_for_update(
                session, schedule_id
            )
            if schedule is None or schedule.status is not NotificationScheduleStatus.PROCESSING:
                return
            next_attempt_number = schedule.attempt_count + 1
            next_attempt_at = self._next_attempt_at(now, next_attempt_number)
            notification_schedules.mark_failed(
                schedule,
                last_error=str(error)[:4000] or error.__class__.__name__,
                next_attempt_at=next_attempt_at,
            )

    def _next_attempt_at(
        self, now: datetime, attempt_number: int
    ) -> datetime | None:
        if attempt_number >= self.max_attempts:
            return None
        delay_index = attempt_number - 1
        if delay_index >= len(RETRY_DELAYS_SECONDS):
            return None
        return now + timedelta(seconds=RETRY_DELAYS_SECONDS[delay_index])

    @staticmethod
    def _content(task: Task, schedule: NotificationSchedule) -> str:
        hours = schedule.lead_time_minutes // 60
        due_at = NotificationScheduler._utc(schedule.due_at_snapshot)
        return (
            f"任务《{task.title}》将在{hours}小时后截止，请及时完成。"
            f"截止时间：{due_at:%Y-%m-%d %H:%M UTC}。"
        )

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
