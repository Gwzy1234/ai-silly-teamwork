from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.ai.schemas import (
    AIFileUpdate,
    AIMemberWorkload,
    AIProjectSnapshot,
    AIProjectSummary,
    AITaskInfo,
)
from silly_teamwork.models.enums import TaskStatus, TaskType
from silly_teamwork.models.project import Project
from silly_teamwork.models.user import User
from silly_teamwork.repositories import (
    files,
    project_members,
    task_assignments,
    task_members,
    tasks,
    users,
)
from silly_teamwork.services.collaboration_access import CollaborationAccessService

OPEN_TASK_STATUSES = frozenset(
    {TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW}
)


class AIToolLayer:
    """Database-facing tools used by the AI service.

    Every method first goes through the existing collaboration access rules and
    returns plain JSON-serializable DTOs for the LLM prompt.
    """

    def __init__(self, access_service: CollaborationAccessService | None = None) -> None:
        self.access = access_service or CollaborationAccessService()

    async def get_project_summary(
        self,
        session: AsyncSession,
        current_user: User,
        project_id: UUID,
    ) -> AIProjectSummary:
        project = await self._require_project(session, current_user, project_id)
        all_tasks = await tasks.list_for_project(session, project_id)
        members = await project_members.list_for_project(session, project_id)
        now = datetime.now(UTC)

        completed_tasks = sum(1 for task in all_tasks if task.status is TaskStatus.DONE)
        open_tasks = sum(1 for task in all_tasks if task.status in OPEN_TASK_STATUSES)
        overdue_tasks = sum(
            1
            for task in all_tasks
            if task.status in OPEN_TASK_STATUSES
            and task.due_at is not None
            and self._as_utc(task.due_at) < now
        )

        return AIProjectSummary(
            project_id=project.id,
            project_name=project.name,
            status=project.status.value,
            starts_at=project.starts_at,
            due_at=project.due_at,
            member_count=len(members),
            total_tasks=len(all_tasks),
            completed_tasks=completed_tasks,
            open_tasks=open_tasks,
            overdue_tasks=overdue_tasks,
        )

    async def get_project_tasks(
        self,
        session: AsyncSession,
        current_user: User,
        project_id: UUID,
    ) -> list[AITaskInfo]:
        await self._require_project(session, current_user, project_id)
        all_tasks = await tasks.list_for_project(session, project_id)
        result: list[AITaskInfo] = []
        for task in all_tasks:
            owner_user_id: UUID | None = None
            owner_display_name: str | None = None
            assignee_user_ids: list[UUID] = []
            if task.task_type is TaskType.COLLABORATIVE:
                task_memberships = await task_members.list_for_task(session, task.id)
                assignee_user_ids = [membership.user_id for membership in task_memberships]
                owner = await task_members.get_owner(session, task.id)
                if owner is not None:
                    owner_user_id = owner.user_id
                    owner_user = await users.get_by_id(session, owner.user_id)
                    if owner_user is not None:
                        owner_display_name = (
                            owner_user.display_name or owner_user.username
                        )
            else:
                assignments = await task_assignments.list_for_task(session, task.id)
                assignee_user_ids = [assignment.user_id for assignment in assignments]

            result.append(
                AITaskInfo(
                    id=task.id,
                    title=task.title,
                    description=task.description,
                    status=task.status.value,
                    priority=task.priority.value,
                    task_type=task.task_type.value,
                    starts_at=task.starts_at,
                    due_at=task.due_at,
                    completed_at=task.completed_at,
                    owner_user_id=owner_user_id,
                    owner_display_name=owner_display_name,
                    assignee_user_ids=assignee_user_ids,
                )
            )
        return result

    async def get_member_workload(
        self,
        session: AsyncSession,
        current_user: User,
        project_id: UUID,
    ) -> list[AIMemberWorkload]:
        await self._require_project(session, current_user, project_id)
        members = await project_members.list_for_project(session, project_id)
        workloads: dict[UUID, AIMemberWorkload] = {}
        for membership in members:
            user = await users.get_by_id(session, membership.user_id)
            if user is None:
                continue
            workloads[user.id] = AIMemberWorkload(
                user_id=user.id,
                username=user.username,
                display_name=user.display_name,
            )

        all_tasks = await tasks.list_for_project(session, project_id)
        now = datetime.now(UTC)
        soon = now + timedelta(days=7)

        for task in all_tasks:
            if task.task_type is TaskType.COLLABORATIVE:
                task_memberships = await task_members.list_for_task(session, task.id)
                task_is_open = task.status in OPEN_TASK_STATUSES
                task_is_overdue = (
                    task_is_open and task.due_at is not None and self._as_utc(task.due_at) < now
                )
                task_is_upcoming = (
                    task_is_open
                    and task.due_at is not None
                    and now <= self._as_utc(task.due_at) <= soon
                )
                for task_membership in task_memberships:
                    workload = workloads.get(task_membership.user_id)
                    if workload is None:
                        continue
                    if task_is_open:
                        workload.open_collaborative_tasks += 1
                    if task_is_overdue:
                        workload.overdue_tasks += 1
                    if task_is_upcoming:
                        workload.upcoming_tasks += 1
            else:
                assignments = await task_assignments.list_for_task(session, task.id)
                for assignment in assignments:
                    workload = workloads.get(assignment.user_id)
                    if workload is None:
                        continue
                    assignment_is_open = assignment.status in OPEN_TASK_STATUSES
                    assignment_is_overdue = (
                        assignment_is_open
                        and task.due_at is not None
                        and self._as_utc(task.due_at) < now
                    )
                    assignment_is_upcoming = (
                        assignment_is_open
                        and task.due_at is not None
                        and now <= self._as_utc(task.due_at) <= soon
                    )
                    if assignment_is_open:
                        workload.open_personal_tasks += 1
                    if assignment_is_overdue:
                        workload.overdue_tasks += 1
                    if assignment_is_upcoming:
                        workload.upcoming_tasks += 1

        for workload in workloads.values():
            workload.total_open_tasks = (
                workload.open_collaborative_tasks + workload.open_personal_tasks
            )
        return list(workloads.values())

    async def get_project_file_updates(
        self,
        session: AsyncSession,
        current_user: User,
        project_id: UUID,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[AIFileUpdate]:
        await self._require_project(session, current_user, project_id)
        scope = await self.access.get_file_access_scope(session, current_user)
        rows = await files.list_project_file_index(
            session,
            project_id,
            can_access_all_files=scope.can_access_all_files,
            leader_team_ids=scope.leader_team_ids,
            accessible_project_ids=scope.project_ids,
            collaborative_task_ids=scope.collaborative_task_ids,
            personal_task_ids=scope.personal_task_ids,
        )
        start_datetime = (
            datetime.combine(start_date, time.min, tzinfo=UTC) if start_date else None
        )
        end_datetime = (
            datetime.combine(end_date, time.max, tzinfo=UTC) if end_date else None
        )

        result: list[AIFileUpdate] = []
        for file, project, task, _, uploader in rows:
            if start_datetime is not None and self._as_utc(file.created_at) < start_datetime:
                continue
            if end_datetime is not None and self._as_utc(file.created_at) > end_datetime:
                continue
            result.append(
                AIFileUpdate(
                    file_id=file.id,
                    name=file.original_name,
                    uploaded_by_id=file.uploaded_by_id,
                    uploaded_by_name=(
                        (uploader.display_name or uploader.username)
                        if uploader is not None
                        else None
                    ),
                    created_at=file.created_at,
                    project_id=project.id,
                    task_id=task.id if task is not None else None,
                    task_title=task.title if task is not None else None,
                )
            )
        return result

    async def get_project_snapshot(
        self,
        session: AsyncSession,
        current_user: User,
        project_id: UUID,
        *,
        include_files: bool = False,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> AIProjectSnapshot:
        await self._require_project(session, current_user, project_id)
        summary = await self.get_project_summary(session, current_user, project_id)
        task_infos = await self.get_project_tasks(session, current_user, project_id)
        workloads = await self.get_member_workload(session, current_user, project_id)
        file_updates: list[AIFileUpdate] = []
        if include_files:
            file_updates = await self.get_project_file_updates(
                session,
                current_user,
                project_id,
                start_date=start_date,
                end_date=end_date,
            )
        return AIProjectSnapshot(
            summary=summary,
            tasks=task_infos,
            workloads=workloads,
            files=file_updates,
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    async def _require_project(
        self,
        session: AsyncSession,
        current_user: User,
        project_id: UUID,
    ) -> Project:
        return await self.access.require_project_access(session, current_user, project_id)


def get_ai_tool_layer() -> AIToolLayer:
    return AIToolLayer()
