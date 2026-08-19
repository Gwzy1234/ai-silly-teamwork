from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.enums import ProjectRole, TaskRole, TaskType, TeamRole
from silly_teamwork.models.file import File
from silly_teamwork.models.project import Project
from silly_teamwork.models.task import Task
from silly_teamwork.models.user import User
from silly_teamwork.repositories import (
    files,
    project_members,
    projects,
    system_admins,
    task_assignments,
    task_members,
    tasks,
    team_members,
    teams,
)
from silly_teamwork.services.exceptions import (
    FileNotFoundError,
    ProjectNotFoundError,
    TaskNotFoundError,
)


@dataclass(frozen=True, slots=True)
class CollaborationFileAccessScope:
    can_access_all_files: bool
    leader_team_ids: frozenset[UUID]
    project_ids: frozenset[UUID]
    collaborative_task_ids: frozenset[UUID]
    personal_task_ids: frozenset[UUID]


class CollaborationAccessService:
    async def get_file_access_scope(
        self, session: AsyncSession, current_user: User
    ) -> CollaborationFileAccessScope:
        """Return the existing collaboration relationships in a query-friendly form."""

        is_system_admin = await system_admins.get_by_user_id(session, current_user.id) is not None
        leader_team_ids = await team_members.list_leader_team_ids(session, current_user.id)
        project_ids = await project_members.list_project_ids_for_user(session, current_user.id)
        collaborative_task_ids = await task_members.list_task_ids_for_user(session, current_user.id)
        personal_task_ids = await task_assignments.list_task_ids_for_user(session, current_user.id)
        return CollaborationFileAccessScope(
            can_access_all_files=is_system_admin,
            leader_team_ids=frozenset(leader_team_ids),
            project_ids=frozenset(project_ids),
            collaborative_task_ids=frozenset(collaborative_task_ids),
            personal_task_ids=frozenset(personal_task_ids),
        )

    async def require_project_file_access(
        self, session: AsyncSession, current_user: User, project_id: UUID
    ) -> Project:
        """Authorize a project-scoped file view without changing project business access."""

        project = await projects.get_by_id(session, project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found")
        if await system_admins.get_by_user_id(session, current_user.id) is not None:
            return project
        if not await self._can_access_project_record(session, current_user.id, project):
            raise ProjectNotFoundError("Project not found")
        return project

    async def require_task_file_access(
        self, session: AsyncSession, current_user: User, task_id: UUID
    ) -> Task:
        """Authorize a task-scoped file view without changing task business access."""

        task = await tasks.get_by_id(session, task_id)
        if task is None:
            raise TaskNotFoundError("Task not found")
        if await system_admins.get_by_user_id(session, current_user.id) is not None:
            return task
        if not await self._can_access_task_record(session, current_user.id, task):
            raise TaskNotFoundError("Task not found")
        return task

    async def can_access_project(
        self, session: AsyncSession, current_user: User, project_id: UUID
    ) -> bool:
        project = await projects.get_by_id(session, project_id)
        if project is None:
            return False
        return await self._can_access_project_record(session, current_user.id, project)

    async def can_receive_project_created_notification(
        self, session: AsyncSession, current_user: User, project_id: UUID
    ) -> bool:
        project = await projects.get_by_id(session, project_id)
        if project is None:
            return False
        return (
            await team_members.get_by_team_and_user(
                session, project.team_id, current_user.id
            )
            is not None
        )

    async def require_project_access(
        self, session: AsyncSession, current_user: User, project_id: UUID
    ) -> Project:
        project = await projects.get_by_id(session, project_id)
        if project is None or not await self._can_access_project_record(
            session, current_user.id, project
        ):
            raise ProjectNotFoundError("Project not found")
        return project

    async def can_access_task(
        self, session: AsyncSession, current_user: User, task_id: UUID
    ) -> bool:
        task = await tasks.get_by_id(session, task_id)
        if task is None:
            return False
        return await self._can_access_task_record(session, current_user.id, task)

    async def can_create_personal_task(
        self, session: AsyncSession, current_user: User, project_id: UUID
    ) -> bool:
        project = await projects.get_by_id(session, project_id)
        if project is None:
            return False
        if await system_admins.get_by_user_id(session, current_user.id) is not None:
            return True
        return await self._is_team_leader(session, project.team_id, current_user.id)

    async def can_view_project_personal_tasks(
        self, session: AsyncSession, current_user: User, project_id: UUID
    ) -> bool:
        return await self.can_create_personal_task(session, current_user, project_id)

    async def can_view_personal_task(
        self, session: AsyncSession, current_user: User, task_id: UUID
    ) -> bool:
        task = await tasks.get_by_id(session, task_id)
        if task is None or task.task_type is not TaskType.PERSONAL:
            return False
        return await self._can_access_task_record(session, current_user.id, task)

    async def can_view_personal_task_progress(
        self, session: AsyncSession, current_user: User, task_id: UUID
    ) -> bool:
        task = await tasks.get_by_id(session, task_id)
        if task is None or task.task_type is not TaskType.PERSONAL:
            return False
        if await system_admins.get_by_user_id(session, current_user.id) is not None:
            return True
        project = await projects.get_by_id(session, task.project_id)
        return project is not None and await self._is_team_leader(
            session, project.team_id, current_user.id
        )

    async def can_access_task_assignment(
        self, session: AsyncSession, current_user: User, assignment_id: UUID
    ) -> bool:
        assignment = await task_assignments.get_by_id(session, assignment_id)
        if assignment is None:
            return False
        if assignment.user_id == current_user.id:
            return True
        return await self.can_view_personal_task_progress(session, current_user, assignment.task_id)

    async def can_update_task_assignment_status(
        self, session: AsyncSession, current_user: User, assignment_id: UUID
    ) -> bool:
        assignment = await task_assignments.get_by_id(session, assignment_id)
        return assignment is not None and assignment.user_id == current_user.id

    async def can_delete_personal_task(
        self, session: AsyncSession, current_user: User, task_id: UUID
    ) -> bool:
        task = await tasks.get_by_id(session, task_id)
        if task is None or task.task_type is not TaskType.PERSONAL:
            return False
        if await system_admins.get_by_user_id(session, current_user.id) is not None:
            return True
        project = await projects.get_by_id(session, task.project_id)
        return project is not None and await self._is_team_leader(
            session, project.team_id, current_user.id
        )

    async def require_task_access(
        self, session: AsyncSession, current_user: User, task_id: UUID
    ) -> Task:
        task = await tasks.get_by_id(session, task_id)
        if task is None or not await self._can_access_task_record(session, current_user.id, task):
            raise TaskNotFoundError("Task not found")
        return task

    async def can_manage_project(
        self, session: AsyncSession, current_user: User, project_id: UUID
    ) -> bool:
        project = await projects.get_by_id(session, project_id)
        if project is None:
            return False
        if await self._is_team_leader(session, project.team_id, current_user.id):
            return True
        membership = await project_members.get_by_project_and_user(
            session, project.id, current_user.id
        )
        return membership is not None and membership.role is ProjectRole.OWNER

    async def can_delete_project(
        self, session: AsyncSession, current_user: User, project_id: UUID
    ) -> bool:
        project = await projects.get_by_id(session, project_id)
        if project is None:
            return False
        if await system_admins.get_by_user_id(session, current_user.id) is not None:
            return True
        return await self._is_team_leader(session, project.team_id, current_user.id)

    async def can_manage_task(
        self, session: AsyncSession, current_user: User, task_id: UUID
    ) -> bool:
        task = await tasks.get_by_id(session, task_id)
        if task is None:
            return False
        if task.task_type is TaskType.PERSONAL:
            return False
        project = await projects.get_by_id(session, task.project_id)
        if project is None:
            return False
        if await self._is_team_leader(session, project.team_id, current_user.id):
            return True
        project_membership = await project_members.get_by_project_and_user(
            session, project.id, current_user.id
        )
        if project_membership is not None and project_membership.role is ProjectRole.OWNER:
            return True
        task_membership = await task_members.get_by_task_and_user(session, task.id, current_user.id)
        return task_membership is not None and task_membership.role is TaskRole.OWNER

    async def can_delete_task(
        self, session: AsyncSession, current_user: User, task_id: UUID
    ) -> bool:
        task = await tasks.get_by_id(session, task_id)
        if task is None:
            return False
        if task.task_type is TaskType.PERSONAL:
            return False
        if await system_admins.get_by_user_id(session, current_user.id) is not None:
            return True
        project = await projects.get_by_id(session, task.project_id)
        if project is None:
            return False
        if await self._is_team_leader(session, project.team_id, current_user.id):
            return True
        project_membership = await project_members.get_by_project_and_user(
            session, project.id, current_user.id
        )
        return project_membership is not None and project_membership.role is ProjectRole.OWNER

    async def can_upload_project_file(
        self, session: AsyncSession, current_user: User, project_id: UUID
    ) -> bool:
        return await self.can_access_project(session, current_user, project_id)

    async def can_upload_task_file(
        self, session: AsyncSession, current_user: User, task_id: UUID
    ) -> bool:
        return await self.can_access_task(session, current_user, task_id)

    async def can_modify_file(
        self, session: AsyncSession, current_user: User, file_id: UUID
    ) -> bool:
        file = await files.get_by_id(session, file_id)
        if file is None:
            return False
        return await self._can_control_file(session, current_user, file)

    async def can_delete_file(
        self, session: AsyncSession, current_user: User, file_id: UUID
    ) -> bool:
        return await self.can_modify_file(session, current_user, file_id)

    async def is_team_leader(
        self, session: AsyncSession, current_user: User, team_id: UUID
    ) -> bool:
        return await self._is_team_leader(session, team_id, current_user.id)

    async def can_delete_team(
        self, session: AsyncSession, current_user: User, team_id: UUID
    ) -> bool:
        if await teams.get_by_id(session, team_id) is None:
            return False
        if await system_admins.get_by_user_id(session, current_user.id) is not None:
            return True
        return await self._is_team_leader(session, team_id, current_user.id)

    async def _can_access_project_record(
        self, session: AsyncSession, user_id: UUID, project: Project
    ) -> bool:
        if await self._is_team_leader(session, project.team_id, user_id):
            return True
        return (
            await project_members.get_by_project_and_user(session, project.id, user_id) is not None
        )

    async def _can_access_task_record(
        self, session: AsyncSession, user_id: UUID, task: Task
    ) -> bool:
        project = await projects.get_by_id(session, task.project_id)
        if project is None:
            return False
        if task.task_type is TaskType.PERSONAL:
            if await system_admins.get_by_user_id(session, user_id) is not None:
                return True
            if await self._is_team_leader(session, project.team_id, user_id):
                return True
            return (
                await task_assignments.get_by_task_and_user(session, task.id, user_id) is not None
            )
        if await self._can_access_project_record(session, user_id, project):
            return True
        return await task_members.get_by_task_and_user(session, task.id, user_id) is not None

    async def _can_control_file(
        self, session: AsyncSession, current_user: User, file: File
    ) -> bool:
        if file.uploaded_by_id == current_user.id:
            return True
        if await system_admins.get_by_user_id(session, current_user.id) is not None:
            return True

        project: Project | None
        if file.project_id is not None:
            project = await projects.get_by_id(session, file.project_id)
        elif file.task_id is not None:
            task = await tasks.get_by_id(session, file.task_id)
            project = None if task is None else await projects.get_by_id(session, task.project_id)
        else:
            return False
        if project is None:
            return False
        if await self._is_team_leader(session, project.team_id, current_user.id):
            return True
        if file.task_id is not None and task is not None and task.task_type is TaskType.PERSONAL:
            return False
        membership = await project_members.get_by_project_and_user(
            session, project.id, current_user.id
        )
        return membership is not None and membership.role is ProjectRole.OWNER

    async def require_file_access(
        self, session: AsyncSession, current_user: User, file: File
    ) -> None:
        if await system_admins.get_by_user_id(session, current_user.id) is not None:
            return
        if file.project_id is not None:
            await self.require_project_file_access(session, current_user, file.project_id)
            return
        if file.task_id is not None:
            await self.require_task_file_access(session, current_user, file.task_id)
            return
        raise FileNotFoundError("File not found")

    @staticmethod
    async def _is_team_leader(session: AsyncSession, team_id: UUID, user_id: UUID) -> bool:
        membership = await team_members.get_by_team_and_user(session, team_id, user_id)
        return membership is not None and membership.role is TeamRole.OWNER


def get_collaboration_access_service() -> CollaborationAccessService:
    return CollaborationAccessService()
