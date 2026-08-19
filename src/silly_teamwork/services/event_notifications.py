from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.enums import NotificationType, TaskType, TeamRole
from silly_teamwork.models.file import File
from silly_teamwork.models.project import Project
from silly_teamwork.models.task import Task
from silly_teamwork.models.user import User
from silly_teamwork.repositories import (
    projects,
    system_admins,
    task_assignments,
    task_members,
    tasks,
    team_members,
)
from silly_teamwork.services.collaboration_access import CollaborationAccessService
from silly_teamwork.services.notifications import NotificationService


class EventNotificationService:
    """Create immediate collaboration notifications inside the caller transaction."""

    def __init__(
        self,
        access_service: CollaborationAccessService | None = None,
        notification_service: NotificationService | None = None,
    ) -> None:
        self.access = access_service or CollaborationAccessService()
        self.notifications = notification_service or NotificationService(self.access)

    async def notify_project_created(
        self,
        session: AsyncSession,
        actor: User,
        project: Project,
    ) -> None:
        for _, recipient in await team_members.list_with_users_for_team(
            session, project.team_id
        ):
            if recipient.id == actor.id:
                continue
            if not await self.access.can_receive_project_created_notification(
                session, recipient, project.id
            ):
                continue
            await self.notifications.create_notification(
                session,
                recipient.id,
                NotificationType.PROJECT_CREATED,
                "新科目",
                f"{self._actor_name(actor)} 创建了新科目《{project.name}》",
                related_project_id=project.id,
                commit=False,
            )

    async def notify_task_created(
        self,
        session: AsyncSession,
        actor: User,
        task: Task,
    ) -> None:
        recipients: dict[UUID, User]
        if task.task_type is TaskType.PERSONAL:
            assignments = await task_assignments.list_for_task(session, task.id)
            recipients = {assignment.user.id: assignment.user for assignment in assignments}
        else:
            memberships = await task_members.list_with_users_for_task(session, task.id)
            recipients = {user.id: user for _, user in memberships}

        for recipient in recipients.values():
            if not await self.access.can_access_task(session, recipient, task.id):
                continue
            await self.notifications.create_notification(
                session,
                recipient.id,
                NotificationType.TASK_CREATED,
                "新任务",
                f"{self._actor_name(actor)} 发布了任务《{task.title}》",
                related_task_id=task.id,
                commit=False,
            )

    async def notify_file_uploaded(
        self,
        session: AsyncSession,
        actor: User,
        file: File,
    ) -> None:
        recipients, task, project = await self._file_recipients(session, file)
        for recipient in recipients.values():
            if recipient.id == actor.id:
                continue
            if project is not None:
                can_access = await self.access.can_access_project(
                    session, recipient, project.id
                )
            elif task is not None:
                can_access = await self.access.can_access_task(
                    session, recipient, task.id
                )
            else:
                can_access = False
            if not can_access:
                continue
            await self.notifications.create_notification(
                session,
                recipient.id,
                NotificationType.FILE_UPLOADED,
                "新文件",
                f"{self._actor_name(actor)} 上传了文件《{file.original_name}》",
                related_file_id=file.id,
                commit=False,
            )

    async def _file_recipients(
        self,
        session: AsyncSession,
        file: File,
    ) -> tuple[dict[UUID, User], Task | None, Project | None]:
        if file.project_id is not None:
            project = await projects.get_by_id(session, file.project_id)
            if project is None:
                return {}, None, None
            return await self._team_users(session, project.team_id), None, project

        if file.task_id is None:
            return {}, None, None
        task = await tasks.get_by_id(session, file.task_id)
        if task is None:
            return {}, None, None
        project = await projects.get_by_id(session, task.project_id)
        if project is None:
            return {}, None, None

        if task.task_type is TaskType.PERSONAL:
            recipients = {
                assignment.user.id: assignment.user
                for assignment in await task_assignments.list_for_task(session, task.id)
            }
            for membership, user in await team_members.list_with_users_for_team(
                session, project.team_id
            ):
                if membership.role is TeamRole.OWNER:
                    recipients[user.id] = user
            for _, user in await system_admins.list_with_users(session):
                recipients[user.id] = user
            return recipients, task, None

        recipients = await self._team_users(session, project.team_id)
        for _, user in await task_members.list_with_users_for_task(session, task.id):
            recipients[user.id] = user
        return recipients, task, None

    @staticmethod
    async def _team_users(session: AsyncSession, team_id: UUID) -> dict[UUID, User]:
        return {
            user.id: user
            for _, user in await team_members.list_with_users_for_team(session, team_id)
        }

    @staticmethod
    def _actor_name(actor: User) -> str:
        return actor.display_name or actor.username


def get_event_notification_service() -> EventNotificationService:
    return EventNotificationService()
