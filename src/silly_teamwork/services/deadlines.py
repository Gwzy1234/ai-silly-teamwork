from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.enums import NotificationType, TaskStatus
from silly_teamwork.models.task import Task
from silly_teamwork.models.user import User
from silly_teamwork.repositories import task_members, tasks
from silly_teamwork.services.collaboration_access import CollaborationAccessService
from silly_teamwork.services.notifications import NotificationService

REMINDABLE_TASK_STATUSES = frozenset(
    {TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW}
)


class DeadlineService:
    def __init__(
        self,
        access_service: CollaborationAccessService | None = None,
        notification_service: NotificationService | None = None,
    ) -> None:
        self.access = access_service or CollaborationAccessService()
        self.notifications = notification_service or NotificationService(self.access)

    async def get_upcoming_tasks(
        self, session: AsyncSession, current_user: User, hours: int
    ) -> list[Task]:
        now = datetime.now(UTC)
        candidates = await tasks.list_due_between(session, now, now + timedelta(hours=hours))
        return await self._filter_accessible(session, current_user, candidates)

    async def get_overdue_tasks(
        self, session: AsyncSession, current_user: User
    ) -> list[Task]:
        candidates = await tasks.list_overdue(session, datetime.now(UTC))
        return await self._filter_accessible(session, current_user, candidates)

    async def create_task_deadline_notifications(
        self, session: AsyncSession, due_soon_hours: int
    ) -> None:
        """Create one unread deadline reminder per task owner, type, and task."""
        now = datetime.now(UTC)
        upcoming = await tasks.list_due_between(
            session, now, now + timedelta(hours=due_soon_hours)
        )
        overdue = await tasks.list_overdue(session, now)
        try:
            for task in upcoming:
                await self._notify_owner(
                    session,
                    task,
                    NotificationType.TASK_DUE_SOON,
                    "任务即将到期",
                    f'任务“{task.title}”将在 {due_soon_hours} 小时内到期',
                )
            for task in overdue:
                await self._notify_owner(
                    session,
                    task,
                    NotificationType.TASK_OVERDUE,
                    "任务已逾期",
                    f'任务“{task.title}”已逾期，请尽快处理',
                )
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    async def _notify_owner(
        self,
        session: AsyncSession,
        task: Task,
        notification_type: NotificationType,
        title: str,
        content: str,
    ) -> None:
        current_status = await tasks.get_status(session, task.id)
        if current_status not in REMINDABLE_TASK_STATUSES:
            return
        owner = await task_members.get_owner(session, task.id)
        if owner is None:
            return
        await self.notifications.create_notification(
            session,
            owner.user_id,
            notification_type,
            title,
            content,
            related_task_id=task.id,
            commit=False,
        )

    async def _filter_accessible(
        self, session: AsyncSession, current_user: User, candidates: list[Task]
    ) -> list[Task]:
        accessible: list[Task] = []
        for task in candidates:
            if await self.access.can_access_task(session, current_user, task.id):
                accessible.append(task)
        return accessible


def get_deadline_service() -> DeadlineService:
    return DeadlineService()
