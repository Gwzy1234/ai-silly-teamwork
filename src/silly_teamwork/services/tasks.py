from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.enums import (
    AttachmentMode,
    ProjectRole,
    TaskRole,
    TaskStatus,
    TaskType,
)
from silly_teamwork.models.project_member import ProjectMember
from silly_teamwork.models.task import Task
from silly_teamwork.models.task_member import TaskMember
from silly_teamwork.models.user import User
from silly_teamwork.repositories import (
    project_members,
    projects,
    task_members,
    tasks,
    team_members,
)
from silly_teamwork.schemas.task import TaskCreate, TaskMemberAdd, TaskUpdate
from silly_teamwork.services.collaboration_access import CollaborationAccessService
from silly_teamwork.services.event_notifications import EventNotificationService
from silly_teamwork.services.exceptions import (
    InvalidStatusTransitionError,
    ProjectAccessDeniedError,
    ProjectMemberNotFoundError,
    ProjectNotFoundError,
    TaskAccessDeniedError,
    TaskMemberConflictError,
    TaskMemberNotFoundError,
    TaskNotFoundError,
)
from silly_teamwork.services.file_cleanup import FileCleanupService
from silly_teamwork.services.notification_schedules import NotificationScheduleService
from silly_teamwork.services.task_deletion import TaskDeletionService
from silly_teamwork.services.task_rules import TASK_TRANSITIONS, validate_task_dates

COLLABORATOR_TRANSITIONS = {
    (TaskStatus.TODO, TaskStatus.IN_PROGRESS),
    (TaskStatus.IN_PROGRESS, TaskStatus.TODO),
    (TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW),
}
REVIEWER_TRANSITIONS = {
    (TaskStatus.IN_REVIEW, TaskStatus.IN_PROGRESS),
    (TaskStatus.IN_REVIEW, TaskStatus.DONE),
}


class TaskService:
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

    async def create_task(
        self,
        session: AsyncSession,
        current_user: User,
        project_id: UUID,
        payload: TaskCreate,
    ) -> Task:
        project = await projects.get_by_id(session, project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found")
        if not await self.access.can_manage_project(session, current_user, project_id):
            raise ProjectAccessDeniedError("Project management permission required")
        owner_id = payload.owner_user_id or current_user.id
        self._validate_dates(payload.starts_at, payload.due_at)
        try:
            await self._ensure_project_member(session, project_id, owner_id)
            task = Task(
                project_id=project_id,
                title=payload.title.strip(),
                description=self._optional_text(payload.description),
                priority=payload.priority,
                starts_at=payload.starts_at,
                due_at=payload.due_at,
                created_by_id=current_user.id,
                task_type=TaskType.COLLABORATIVE,
                attachment_mode=AttachmentMode.SHARED,
            )
            tasks.add(session, task)
            await session.flush()
            task_members.add(
                session,
                TaskMember(task_id=task.id, user_id=owner_id, role=TaskRole.OWNER),
            )
            await session.flush()
            await self.schedules.create_task_deadline_schedules(session, task)
            await self.events.notify_task_created(session, current_user, task)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        return task

    async def get_task(
        self, session: AsyncSession, current_user: User, task_id: UUID
    ) -> Task:
        return await self.access.require_task_access(session, current_user, task_id)

    async def list_tasks(
        self, session: AsyncSession, current_user: User, project_id: UUID
    ) -> list[Task]:
        await self.access.require_project_access(session, current_user, project_id)
        return await tasks.list_for_project(
            session, project_id, task_type=TaskType.COLLABORATIVE
        )

    async def update_task(
        self,
        session: AsyncSession,
        current_user: User,
        task_id: UUID,
        payload: TaskUpdate,
    ) -> Task:
        task = await self._require_manage(session, current_user, task_id)
        values = payload.model_dump(exclude_unset=True)
        due_at_changed = "due_at" in values and values["due_at"] != task.due_at
        starts_at = values.get("starts_at", task.starts_at)
        due_at = values.get("due_at", task.due_at)
        self._validate_dates(starts_at, due_at)
        try:
            for field, value in values.items():
                if field == "title":
                    value = value.strip()
                elif field == "description":
                    value = self._optional_text(value)
                setattr(task, field, value)
            if due_at_changed:
                await self.schedules.rebuild_task_deadline_schedules(session, task)
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        return task

    async def delete_task(
        self, session: AsyncSession, current_user: User, task_id: UUID
    ) -> None:
        task = await tasks.get_by_id(session, task_id)
        if task is None:
            raise TaskNotFoundError("Task not found")
        self._require_collaborative(task)
        if not await self.access.can_delete_task(session, current_user, task_id):
            raise TaskAccessDeniedError("Task deletion permission required")
        await self.deletion.delete(session, task)

    async def change_status(
        self,
        session: AsyncSession,
        current_user: User,
        task_id: UUID,
        target: TaskStatus,
    ) -> Task:
        task = await self.access.require_task_access(session, current_user, task_id)
        self._require_collaborative(task)
        if target is task.status:
            return task
        if target not in TASK_TRANSITIONS[task.status]:
            raise InvalidStatusTransitionError(
                f"Task status cannot transition from {task.status.value} to {target.value}"
            )
        can_manage = await self.access.can_manage_task(session, current_user, task_id)
        if not can_manage:
            membership = await task_members.get_by_task_and_user(
                session, task_id, current_user.id
            )
            transition = (task.status, target)
            allowed = membership is not None and (
                (
                    membership.role is TaskRole.COLLABORATOR
                    and transition in COLLABORATOR_TRANSITIONS
                )
                or (membership.role is TaskRole.REVIEWER and transition in REVIEWER_TRANSITIONS)
            )
            if not allowed:
                raise TaskAccessDeniedError("Task status permission required")
        try:
            previous_status = task.status
            task.status = target
            if target is TaskStatus.DONE:
                task.completed_at = datetime.now(UTC)
            elif task.completed_at is not None:
                task.completed_at = None
            if target in {TaskStatus.DONE, TaskStatus.CANCELLED}:
                await self.schedules.cancel_task_deadline_schedules(session, task)
            elif previous_status in {TaskStatus.DONE, TaskStatus.CANCELLED}:
                await self.schedules.rebuild_task_deadline_schedules(session, task)
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        return task

    async def list_members(
        self, session: AsyncSession, current_user: User, task_id: UUID
    ) -> list[TaskMember]:
        task = await self.access.require_task_access(session, current_user, task_id)
        self._require_collaborative(task)
        return await task_members.list_for_task(session, task_id)

    async def add_member(
        self,
        session: AsyncSession,
        current_user: User,
        task_id: UUID,
        payload: TaskMemberAdd,
    ) -> TaskMember:
        task = await self._require_manage(session, current_user, task_id)
        self._require_collaborative(task)
        await self._require_project_member(session, task.project_id, payload.user_id)
        if await task_members.get_by_task_and_user(session, task_id, payload.user_id) is not None:
            raise TaskMemberConflictError("User is already a task member")
        try:
            membership = TaskMember(
                task_id=task_id,
                user_id=payload.user_id,
                role=payload.role,
            )
            task_members.add(session, membership)
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        return membership

    async def remove_member(
        self,
        session: AsyncSession,
        current_user: User,
        task_id: UUID,
        user_id: UUID,
    ) -> None:
        task = await self._require_manage(session, current_user, task_id)
        self._require_collaborative(task)
        membership = await task_members.get_by_task_and_user(session, task_id, user_id)
        if membership is None:
            raise TaskMemberNotFoundError("Task member not found")
        if membership.role is TaskRole.OWNER:
            raise TaskMemberConflictError("Transfer task ownership before removing the owner")
        try:
            await task_members.delete(session, membership)
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    async def transfer_owner(
        self,
        session: AsyncSession,
        current_user: User,
        task_id: UUID,
        new_owner_user_id: UUID,
    ) -> TaskMember:
        task = await tasks.get_by_id(session, task_id)
        if task is None:
            raise TaskNotFoundError("Task not found")
        self._require_collaborative(task)
        if not await self.access.can_manage_project(session, current_user, task.project_id):
            raise TaskAccessDeniedError("Project management permission required")
        await self._require_project_member(session, task.project_id, new_owner_user_id)
        try:
            await tasks.get_by_id_for_update(session, task_id)
            old_owner = await task_members.get_owner(session, task_id, for_update=True)
            if old_owner is None:
                raise TaskMemberNotFoundError("Task owner not found")
            if old_owner.user_id == new_owner_user_id:
                return old_owner
            new_owner = await task_members.get_by_task_and_user(
                session, task_id, new_owner_user_id
            )
            if new_owner is None:
                new_owner = TaskMember(
                    task_id=task_id,
                    user_id=new_owner_user_id,
                    role=TaskRole.COLLABORATOR,
                )
                task_members.add(session, new_owner)
                await session.flush()
            old_owner.role = TaskRole.COLLABORATOR
            await session.flush()
            new_owner.role = TaskRole.OWNER
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        return new_owner

    async def _require_manage(
        self, session: AsyncSession, current_user: User, task_id: UUID
    ) -> Task:
        task = await tasks.get_by_id(session, task_id)
        if task is None:
            raise TaskNotFoundError("Task not found")
        self._require_collaborative(task)
        if not await self.access.can_manage_task(session, current_user, task_id):
            raise TaskAccessDeniedError("Task management permission required")
        return task

    @staticmethod
    async def _require_project_member(
        session: AsyncSession, project_id: UUID, user_id: UUID
    ) -> ProjectMember:
        membership = await project_members.get_by_project_and_user(session, project_id, user_id)
        if membership is None:
            raise ProjectMemberNotFoundError("User is not a project member")
        return membership

    @staticmethod
    async def _ensure_project_member(
        session: AsyncSession, project_id: UUID, user_id: UUID
    ) -> ProjectMember:
        membership = await project_members.get_by_project_and_user(session, project_id, user_id)
        if membership is not None:
            return membership
        project = await projects.get_by_id(session, project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found")
        if await team_members.get_by_team_and_user(session, project.team_id, user_id) is None:
            raise ProjectMemberNotFoundError("Task owner must belong to the project team")
        membership = ProjectMember(
            project_id=project_id,
            user_id=user_id,
            role=ProjectRole.MEMBER,
        )
        project_members.add(session, membership)
        await session.flush()
        return membership

    @staticmethod
    def _validate_dates(starts_at: datetime | None, due_at: datetime | None) -> None:
        validate_task_dates(starts_at, due_at)

    @staticmethod
    def _require_collaborative(task: Task) -> None:
        if task.task_type is not TaskType.COLLABORATIVE:
            raise TaskAccessDeniedError("Collaborative task operation required")

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


def get_task_service() -> TaskService:
    return TaskService()
