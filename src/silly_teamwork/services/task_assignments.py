from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.enums import TaskStatus
from silly_teamwork.models.task_assignment import TaskAssignment
from silly_teamwork.models.user import User
from silly_teamwork.repositories import task_assignments
from silly_teamwork.repositories.task_assignments import TaskAssignmentCounts
from silly_teamwork.services.collaboration_access import CollaborationAccessService
from silly_teamwork.services.exceptions import (
    InvalidStatusTransitionError,
    TaskAssignmentAccessDeniedError,
    TaskAssignmentNotFoundError,
)
from silly_teamwork.services.notification_schedules import NotificationScheduleService
from silly_teamwork.services.task_rules import TASK_TRANSITIONS

EXECUTING_ASSIGNMENT_STATUSES = frozenset(
    {TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW, TaskStatus.DONE}
)


class TaskAssignmentService:
    def __init__(
        self,
        access_service: CollaborationAccessService | None = None,
        schedule_service: NotificationScheduleService | None = None,
    ) -> None:
        self.access = access_service or CollaborationAccessService()
        self.schedules = schedule_service or NotificationScheduleService()

    async def get_assignment(
        self, session: AsyncSession, current_user: User, assignment_id: UUID
    ) -> TaskAssignment:
        assignment = await task_assignments.get_by_id(session, assignment_id)
        if assignment is None or not await self.access.can_access_task_assignment(
            session, current_user, assignment_id
        ):
            raise TaskAssignmentNotFoundError("Task assignment not found")
        return assignment

    async def list_my_assignments(
        self,
        session: AsyncSession,
        current_user: User,
        *,
        status: TaskStatus | None = None,
        team_id: UUID | None = None,
        project_id: UUID | None = None,
        due_before: datetime | None = None,
        due_after: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TaskAssignment]:
        return await task_assignments.list_for_user(
            session,
            current_user.id,
            status=status,
            team_id=team_id,
            project_id=project_id,
            due_before=due_before,
            due_after=due_after,
            limit=limit,
            offset=offset,
        )

    async def get_my_assignment_for_task(
        self,
        session: AsyncSession,
        current_user: User,
        task_id: UUID,
    ) -> TaskAssignment | None:
        return await task_assignments.get_by_task_and_user(session, task_id, current_user.id)

    async def count_my_assignments(
        self,
        session: AsyncSession,
        current_user: User,
    ) -> TaskAssignmentCounts:
        return await task_assignments.count_for_user(session, current_user.id)

    async def change_status(
        self,
        session: AsyncSession,
        current_user: User,
        assignment_id: UUID,
        target: TaskStatus,
    ) -> TaskAssignment:
        assignment = await task_assignments.get_by_id(session, assignment_id)
        if assignment is None:
            raise TaskAssignmentNotFoundError("Task assignment not found")
        if not await self.access.can_update_task_assignment_status(
            session, current_user, assignment_id
        ):
            raise TaskAssignmentAccessDeniedError("Only the assigned user can change this status")
        if target is assignment.status:
            return assignment

        try:
            locked = await task_assignments.get_by_id_for_update(session, assignment_id)
            if locked is None:
                raise TaskAssignmentNotFoundError("Task assignment not found")
            if target is locked.status:
                await session.commit()
                return locked
            if target not in TASK_TRANSITIONS[locked.status]:
                raise InvalidStatusTransitionError(
                    "Task assignment status cannot transition "
                    f"from {locked.status.value} to {target.value}"
                )
            now = datetime.now(UTC)
            previous_status = locked.status
            if locked.started_at is None and target in EXECUTING_ASSIGNMENT_STATUSES:
                locked.started_at = now
            locked.status = target
            if target is TaskStatus.DONE:
                locked.completed_at = now
            elif locked.completed_at is not None:
                locked.completed_at = None
            if target in {TaskStatus.DONE, TaskStatus.CANCELLED}:
                await self.schedules.cancel_assignment_deadline_schedules(
                    session, locked
                )
            elif previous_status in {TaskStatus.DONE, TaskStatus.CANCELLED}:
                await self.schedules.rebuild_assignment_deadline_schedules(
                    session, locked
                )
            await session.flush()
            await session.commit()
            await session.refresh(locked)
        except Exception:
            await session.rollback()
            raise
        return locked


def get_task_assignment_service() -> TaskAssignmentService:
    return TaskAssignmentService()
