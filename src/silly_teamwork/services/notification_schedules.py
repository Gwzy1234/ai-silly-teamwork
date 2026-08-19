from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.enums import (
    NotificationScheduleStatus,
    NotificationType,
    TaskStatus,
    TaskType,
)
from silly_teamwork.models.notification_schedule import NotificationSchedule
from silly_teamwork.models.task import Task
from silly_teamwork.models.task_assignment import TaskAssignment
from silly_teamwork.repositories import (
    notification_schedules,
    task_assignments,
    task_members,
    tasks,
)

DEADLINE_LEAD_TIME_MINUTES = (4320, 2880, 1440, 720, 480)
REMINDABLE_STATUSES = frozenset(
    {TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW}
)
Clock = Callable[[], datetime]


class NotificationScheduleService:
    def __init__(self, now_provider: Clock | None = None) -> None:
        self._now = now_provider or (lambda: datetime.now(UTC))

    async def create_task_deadline_schedules(
        self,
        session: AsyncSession,
        task: Task,
    ) -> list[NotificationSchedule]:
        if (
            task.task_type is not TaskType.COLLABORATIVE
            or task.due_at is None
            or task.status not in REMINDABLE_STATUSES
        ):
            return []
        owner = await task_members.get_owner(session, task.id)
        if owner is None:
            return []
        active = await notification_schedules.list_active_for_task(session, task.id)
        return await self._create_missing_schedules(
            session,
            task=task,
            user_id=owner.user_id,
            active=active,
        )

    async def create_assignment_deadline_schedules(
        self,
        session: AsyncSession,
        assignment: TaskAssignment,
    ) -> list[NotificationSchedule]:
        if assignment.status not in REMINDABLE_STATUSES:
            return []
        task = await tasks.get_by_id(session, assignment.task_id)
        if task is None or task.task_type is not TaskType.PERSONAL or task.due_at is None:
            return []
        active = await notification_schedules.list_active_for_assignment(
            session, assignment.id
        )
        return await self._create_missing_schedules(
            session,
            task=task,
            user_id=assignment.user_id,
            active=active,
            assignment=assignment,
        )

    async def cancel_task_deadline_schedules(
        self,
        session: AsyncSession,
        task: Task,
    ) -> int:
        return await notification_schedules.cancel_pending_for_task(
            session,
            task.id,
            cancelled_at=self._now(),
        )

    async def cancel_assignment_deadline_schedules(
        self,
        session: AsyncSession,
        assignment: TaskAssignment,
    ) -> int:
        return await notification_schedules.cancel_pending_for_assignment(
            session,
            assignment.id,
            cancelled_at=self._now(),
        )

    async def rebuild_task_deadline_schedules(
        self,
        session: AsyncSession,
        task: Task,
    ) -> list[NotificationSchedule]:
        now = self._now()
        if task.task_type is TaskType.COLLABORATIVE:
            await notification_schedules.cancel_pending_for_task(
                session,
                task.id,
                cancelled_at=now,
            )
            return await self.create_task_deadline_schedules(session, task)

        await notification_schedules.cancel_pending_for_task_assignments(
            session,
            task.id,
            cancelled_at=now,
        )
        created: list[NotificationSchedule] = []
        for assignment in await task_assignments.list_for_task(session, task.id):
            created.extend(
                await self.create_assignment_deadline_schedules(session, assignment)
            )
        return created

    async def rebuild_assignment_deadline_schedules(
        self,
        session: AsyncSession,
        assignment: TaskAssignment,
    ) -> list[NotificationSchedule]:
        await notification_schedules.cancel_pending_for_assignment(
            session,
            assignment.id,
            cancelled_at=self._now(),
        )
        return await self.create_assignment_deadline_schedules(session, assignment)

    async def _create_missing_schedules(
        self,
        session: AsyncSession,
        *,
        task: Task,
        user_id: UUID,
        active: list[NotificationSchedule],
        assignment: TaskAssignment | None = None,
    ) -> list[NotificationSchedule]:
        if task.due_at is None:
            return []
        due_at = self._as_utc(task.due_at)
        now = self._as_utc(self._now())
        active_nodes = {
            schedule.lead_time_minutes
            for schedule in active
            if schedule.notification_type is NotificationType.TASK_DUE_SOON
        }
        created: list[NotificationSchedule] = []
        for lead_time_minutes in DEADLINE_LEAD_TIME_MINUTES:
            scheduled_for = due_at - timedelta(minutes=lead_time_minutes)
            if lead_time_minutes in active_nodes or scheduled_for <= now:
                continue
            created.append(
                NotificationSchedule(
                    user_id=user_id,
                    notification_type=NotificationType.TASK_DUE_SOON,
                    task_id=task.id if assignment is None else None,
                    task_assignment_id=None if assignment is None else assignment.id,
                    lead_time_minutes=lead_time_minutes,
                    scheduled_for=scheduled_for,
                    due_at_snapshot=due_at,
                    status=NotificationScheduleStatus.PENDING,
                )
            )
        if created:
            notification_schedules.add_all(session, created)
            await session.flush()
        return created

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def get_notification_schedule_service() -> NotificationScheduleService:
    return NotificationScheduleService()
