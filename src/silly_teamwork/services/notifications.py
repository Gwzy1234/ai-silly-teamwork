from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.enums import NotificationType
from silly_teamwork.models.notification import Notification
from silly_teamwork.models.user import User
from silly_teamwork.repositories import files, notifications, users
from silly_teamwork.services.collaboration_access import CollaborationAccessService
from silly_teamwork.services.exceptions import (
    InvalidNotificationError,
    NotificationNotFoundError,
)


class NotificationService:
    def __init__(self, access_service: CollaborationAccessService | None = None) -> None:
        self.access = access_service or CollaborationAccessService()

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
        related_file_id: UUID | None = None,
        commit: bool = True,
        deduplicate: bool = True,
    ) -> Notification:
        user = await users.get_by_id(session, user_id)
        if user is None:
            raise NotificationNotFoundError("Notification recipient not found")
        self._validate_related_resource(
            notification_type,
            related_task_id,
            related_project_id,
            related_file_id,
        )
        if related_task_id is not None:
            await self.access.require_task_access(session, user, related_task_id)
        if related_project_id is not None:
            if notification_type is NotificationType.PROJECT_CREATED:
                allowed = await self.access.can_receive_project_created_notification(
                    session, user, related_project_id
                )
                if not allowed:
                    raise NotificationNotFoundError("Notification recipient cannot access project")
            else:
                await self.access.require_project_access(session, user, related_project_id)
        if related_file_id is not None:
            file = await files.get_file(session, related_file_id)
            if file is None:
                raise NotificationNotFoundError("Notification file not found")
            await self.access.require_file_access(session, user, file)

        normalized_title = title.strip()
        normalized_content = content.strip()
        is_task_deadline_reminder = notification_type in {
            NotificationType.TASK_DUE_SOON,
            NotificationType.TASK_OVERDUE,
        }
        is_business_event = notification_type in {
            NotificationType.PROJECT_CREATED,
            NotificationType.TASK_CREATED,
            NotificationType.FILE_UPLOADED,
        }
        deduplicate_by_resource = is_task_deadline_reminder or is_business_event
        if deduplicate:
            existing = await notifications.find_matching_unread(
                session,
                user_id=user_id,
                notification_type=notification_type,
                title=None if deduplicate_by_resource else normalized_title,
                content=None if deduplicate_by_resource else normalized_content,
                related_task_id=related_task_id,
                related_project_id=related_project_id,
                related_file_id=related_file_id,
                unread_only=not is_business_event,
            )
            if existing is not None:
                return existing

        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=normalized_title,
            content=normalized_content,
            related_task_id=related_task_id,
            related_project_id=related_project_id,
            related_file_id=related_file_id,
        )
        try:
            notifications.add(session, notification)
            await session.flush()
            if commit:
                await session.commit()
        except Exception:
            if commit:
                await session.rollback()
            raise
        return notification

    async def list_user_notifications(
        self, session: AsyncSession, current_user: User
    ) -> list[Notification]:
        return await notifications.list_for_user(session, current_user.id)

    async def mark_as_read(
        self, session: AsyncSession, current_user: User, notification_id: UUID
    ) -> Notification:
        notification = await notifications.get_for_user(
            session, notification_id, current_user.id
        )
        if notification is None:
            raise NotificationNotFoundError("Notification not found")
        if notification.is_read:
            return notification
        try:
            notification.is_read = True
            notification.read_at = datetime.now(UTC)
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        return notification

    async def mark_all_as_read(self, session: AsyncSession, current_user: User) -> int:
        try:
            count = await notifications.mark_all_as_read(
                session, current_user.id, read_at=datetime.now(UTC)
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        return count

    @staticmethod
    def _validate_related_resource(
        notification_type: NotificationType,
        related_task_id: UUID | None,
        related_project_id: UUID | None,
        related_file_id: UUID | None,
    ) -> None:
        related_count = sum(
            item is not None
            for item in (related_task_id, related_project_id, related_file_id)
        )
        if related_count > 1:
            raise InvalidNotificationError("Notification can reference only one resource")
        if notification_type in {
            NotificationType.TASK_DUE_SOON,
            NotificationType.TASK_OVERDUE,
            NotificationType.TASK_CREATED,
        } and related_task_id is None:
            raise InvalidNotificationError("Task notification requires related_task_id")
        if (
            notification_type
            in {NotificationType.PROJECT_DUE_SOON, NotificationType.PROJECT_CREATED}
            and related_project_id is None
        ):
            raise InvalidNotificationError("Project notification requires related_project_id")
        if (
            notification_type is NotificationType.FILE_UPLOADED
            and related_file_id is None
        ):
            raise InvalidNotificationError("File notification requires related_file_id")


def get_notification_service() -> NotificationService:
    return NotificationService()
