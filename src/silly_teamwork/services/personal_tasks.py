from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.enums import AttachmentMode, TaskStatus, TaskType
from silly_teamwork.models.task import Task
from silly_teamwork.models.task_assignment import TaskAssignment
from silly_teamwork.models.user import User
from silly_teamwork.repositories import projects, task_assignments, tasks, team_members
from silly_teamwork.repositories.task_assignments import PersonalTaskAggregate
from silly_teamwork.schemas.personal_task import PersonalTaskCreate
from silly_teamwork.services.collaboration_access import CollaborationAccessService
from silly_teamwork.services.event_notifications import EventNotificationService
from silly_teamwork.services.exceptions import (
    PersonalTaskValidationError,
    ProjectAccessDeniedError,
    ProjectNotFoundError,
    TaskAccessDeniedError,
    TaskNotFoundError,
)
from silly_teamwork.services.file_cleanup import FileCleanupService
from silly_teamwork.services.notification_schedules import NotificationScheduleService
from silly_teamwork.services.task_deletion import TaskDeletionService
from silly_teamwork.services.task_rules import validate_task_dates


class PersonalTaskService:
    def __init__(
        self,
        access_service: CollaborationAccessService | None = None,
        cleanup_service: FileCleanupService | None = None,
        schedule_service: NotificationScheduleService | None = None,
        event_notification_service: EventNotificationService | None = None,
    ) -> None:
        self.access = access_service or CollaborationAccessService()
        self.deletion = TaskDeletionService(cleanup_service)
        self.schedules = schedule_service or NotificationScheduleService()
        self.events = event_notification_service or EventNotificationService(self.access)

    async def create_personal_task(
        self,
        session: AsyncSession,
        current_user: User,
        project_id: UUID,
        payload: PersonalTaskCreate,
    ) -> Task:
        project = await projects.get_by_id(session, project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found")
        if not await self.access.can_create_personal_task(session, current_user, project_id):
            raise ProjectAccessDeniedError("Personal task creation permission required")
        self._validate_payload(payload)
        await self._validate_assignees(session, project.team_id, payload.assignee_user_ids)

        task = Task(
            project_id=project_id,
            title=payload.title,
            description=self._optional_text(payload.description),
            priority=payload.priority,
            starts_at=payload.starts_at,
            due_at=payload.due_at,
            created_by_id=current_user.id,
            task_type=TaskType.PERSONAL,
            attachment_mode=AttachmentMode.SHARED,
        )
        try:
            tasks.add(session, task)
            await session.flush()
            assignments = [
                TaskAssignment(
                    task=task,
                    user_id=user_id,
                    status=TaskStatus.TODO,
                )
                for user_id in payload.assignee_user_ids
            ]
            task_assignments.add_all(
                session,
                assignments,
            )
            await session.flush()
            for assignment in assignments:
                await self.schedules.create_assignment_deadline_schedules(
                    session, assignment
                )
            await self.events.notify_task_created(session, current_user, task)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        return task

    async def get_personal_task(
        self, session: AsyncSession, current_user: User, task_id: UUID
    ) -> Task:
        task = await self._require_personal_task(session, task_id)
        if not await self.access.can_view_personal_task(session, current_user, task_id):
            raise TaskNotFoundError("Task not found")
        return task

    async def list_project_personal_tasks(
        self,
        session: AsyncSession,
        current_user: User,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[PersonalTaskAggregate], int]:
        project = await projects.get_by_id(session, project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found")
        if not await self.access.can_view_project_personal_tasks(session, current_user, project_id):
            raise ProjectAccessDeniedError("Personal task management permission required")
        return await task_assignments.list_personal_task_aggregates_for_project(
            session,
            project_id,
            limit=limit,
            offset=offset,
        )

    async def list_assignments(
        self, session: AsyncSession, current_user: User, task_id: UUID
    ) -> list[TaskAssignment]:
        await self._require_personal_task(session, task_id)
        if not await self.access.can_view_personal_task_progress(session, current_user, task_id):
            raise TaskAccessDeniedError("Personal task progress permission required")
        return await task_assignments.list_for_task(session, task_id)

    async def delete_personal_task(
        self, session: AsyncSession, current_user: User, task_id: UUID
    ) -> None:
        task = await self._require_personal_task(session, task_id)
        if not await self.access.can_delete_personal_task(session, current_user, task_id):
            raise TaskAccessDeniedError("Personal task deletion permission required")
        await self.deletion.delete(session, task)

    @staticmethod
    def _validate_payload(payload: PersonalTaskCreate) -> None:
        if payload.attachment_mode is not AttachmentMode.SHARED:
            raise PersonalTaskValidationError("Individual attachments are not supported in V1.2")
        if not payload.assignee_user_ids:
            raise PersonalTaskValidationError("At least one personal task assignee is required")
        if len(payload.assignee_user_ids) != len(set(payload.assignee_user_ids)):
            raise PersonalTaskValidationError("Personal task assignees must be unique")
        validate_task_dates(payload.starts_at, payload.due_at)

    @staticmethod
    async def _validate_assignees(
        session: AsyncSession, team_id: UUID, assignee_user_ids: list[UUID]
    ) -> None:
        existing_user_ids = await team_members.list_existing_user_ids(
            session, team_id, assignee_user_ids
        )
        if existing_user_ids != set(assignee_user_ids):
            raise PersonalTaskValidationError(
                "Every personal task assignee must belong to the project team"
            )

    @staticmethod
    async def _require_personal_task(session: AsyncSession, task_id: UUID) -> Task:
        task = await tasks.get_by_id_with_project_team(session, task_id)
        if task is None or task.task_type is not TaskType.PERSONAL:
            raise TaskNotFoundError("Personal task not found")
        return task

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


def get_personal_task_service() -> PersonalTaskService:
    return PersonalTaskService()
