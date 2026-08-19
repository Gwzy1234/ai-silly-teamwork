from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.enums import ProjectRole, ProjectStatus, TeamRole
from silly_teamwork.models.project import Project
from silly_teamwork.models.project_member import ProjectMember
from silly_teamwork.models.user import User
from silly_teamwork.repositories import (
    files,
    project_members,
    projects,
    task_members,
    team_members,
    teams,
    users,
)
from silly_teamwork.schemas.project import ProjectCreate, ProjectMemberAdd, ProjectUpdate
from silly_teamwork.services.collaboration_access import CollaborationAccessService
from silly_teamwork.services.event_notifications import EventNotificationService
from silly_teamwork.services.exceptions import (
    InvalidDeadlineError,
    InvalidStatusTransitionError,
    ProjectAccessDeniedError,
    ProjectMemberConflictError,
    ProjectMemberNotFoundError,
    ProjectNotFoundError,
    TeamNotFoundError,
)
from silly_teamwork.services.file_cleanup import FileCleanupService

PROJECT_TRANSITIONS: dict[ProjectStatus, frozenset[ProjectStatus]] = {
    ProjectStatus.PLANNING: frozenset({ProjectStatus.ACTIVE, ProjectStatus.ARCHIVED}),
    ProjectStatus.ACTIVE: frozenset({ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED}),
    ProjectStatus.COMPLETED: frozenset({ProjectStatus.ACTIVE, ProjectStatus.ARCHIVED}),
    ProjectStatus.ARCHIVED: frozenset({ProjectStatus.PLANNING}),
}


class ProjectService:
    def __init__(
        self,
        access_service: CollaborationAccessService | None = None,
        cleanup_service: FileCleanupService | None = None,
        event_notification_service: EventNotificationService | None = None,
    ) -> None:
        self.access = access_service or CollaborationAccessService()
        self.cleanup = cleanup_service or FileCleanupService()
        self.events = event_notification_service or EventNotificationService(self.access)

    async def create_project(
        self,
        session: AsyncSession,
        current_user: User,
        team_id: UUID,
        payload: ProjectCreate,
    ) -> Project:
        team = await teams.get_by_id(session, team_id)
        if team is None:
            raise TeamNotFoundError("Team not found")
        if not await self.access.is_team_leader(session, current_user, team_id):
            raise ProjectAccessDeniedError("Only the team leader can create projects")

        owner_id = payload.owner_user_id or current_user.id
        await self._require_team_member(session, team_id, owner_id)
        self._validate_dates(payload.starts_at, payload.due_at)
        try:
            project = Project(
                team_id=team_id,
                name=payload.name.strip(),
                description=self._optional_text(payload.description),
                starts_at=payload.starts_at,
                due_at=payload.due_at,
                created_by_id=current_user.id,
            )
            projects.add(session, project)
            await session.flush()
            project_members.add(
                session,
                ProjectMember(
                    project_id=project.id,
                    user_id=owner_id,
                    role=ProjectRole.OWNER,
                ),
            )
            await session.flush()
            await self.events.notify_project_created(session, current_user, project)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        return project

    async def get_project(
        self, session: AsyncSession, current_user: User, project_id: UUID
    ) -> Project:
        return await self.access.require_project_access(session, current_user, project_id)

    async def list_projects(
        self, session: AsyncSession, current_user: User, team_id: UUID
    ) -> list[Project]:
        team = await teams.get_by_id(session, team_id)
        if team is None:
            raise TeamNotFoundError("Team not found")
        team_membership = await team_members.get_by_team_and_user(
            session, team_id, current_user.id
        )
        if team_membership is None:
            raise TeamNotFoundError("Team not found")
        if team_membership.role is TeamRole.OWNER:
            return await projects.list_for_team(session, team_id)
        return await projects.list_for_user_in_team(session, team_id, current_user.id)

    async def update_project(
        self,
        session: AsyncSession,
        current_user: User,
        project_id: UUID,
        payload: ProjectUpdate,
    ) -> Project:
        project = await self._require_manage(session, current_user, project_id)
        values = payload.model_dump(exclude_unset=True)
        starts_at = values.get("starts_at", project.starts_at)
        due_at = values.get("due_at", project.due_at)
        self._validate_dates(starts_at, due_at)
        target_status = values.get("status")
        if target_status is not None and target_status != project.status:
            self._validate_project_transition(project.status, target_status)
            if (
                target_status is ProjectStatus.ARCHIVED
                or project.status is ProjectStatus.ARCHIVED
            ) and not await self.access.is_team_leader(session, current_user, project.team_id):
                raise ProjectAccessDeniedError(
                    "Only the team leader can archive or restore projects"
                )
        try:
            for field, value in values.items():
                if field == "name":
                    value = value.strip()
                elif field == "description":
                    value = self._optional_text(value)
                setattr(project, field, value)
            if target_status is ProjectStatus.COMPLETED:
                project.completed_at = datetime.now(UTC)
            elif target_status is not None and project.completed_at is not None:
                project.completed_at = None
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        return project

    async def delete_project(
        self, session: AsyncSession, current_user: User, project_id: UUID
    ) -> None:
        project = await projects.get_by_id(session, project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found")
        if not await self.access.can_delete_project(session, current_user, project_id):
            raise ProjectAccessDeniedError("Project deletion permission required")

        project_files = await files.list_all_for_project(session, project_id)
        cleanup_batch = await self.cleanup.stage(file.storage_key for file in project_files)
        try:
            await projects.delete(session, project)
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            await self.cleanup.restore(cleanup_batch)
            raise
        await self.cleanup.finish(cleanup_batch)

    async def list_members(
        self, session: AsyncSession, current_user: User, project_id: UUID
    ) -> list[ProjectMember]:
        await self.access.require_project_access(session, current_user, project_id)
        return await project_members.list_for_project(session, project_id)

    async def add_member(
        self,
        session: AsyncSession,
        current_user: User,
        project_id: UUID,
        payload: ProjectMemberAdd,
    ) -> ProjectMember:
        project = await self._require_manage(session, current_user, project_id)
        await self._require_team_member(session, project.team_id, payload.user_id)
        if await project_members.get_by_project_and_user(
            session, project_id, payload.user_id
        ) is not None:
            raise ProjectMemberConflictError("User is already a project member")
        try:
            membership = ProjectMember(
                project_id=project_id,
                user_id=payload.user_id,
                role=ProjectRole.MEMBER,
            )
            project_members.add(session, membership)
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
        project_id: UUID,
        user_id: UUID,
    ) -> None:
        await self._require_manage(session, current_user, project_id)
        membership = await project_members.get_by_project_and_user(session, project_id, user_id)
        if membership is None:
            raise ProjectMemberNotFoundError("Project member not found")
        if membership.role is ProjectRole.OWNER:
            raise ProjectMemberConflictError("Transfer project ownership before removing the owner")
        try:
            await task_members.delete_for_user_in_project(session, project_id, user_id)
            await project_members.delete(session, membership)
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    async def transfer_owner(
        self,
        session: AsyncSession,
        current_user: User,
        project_id: UUID,
        new_owner_user_id: UUID,
    ) -> ProjectMember:
        project = await self._require_manage(session, current_user, project_id)
        await self._require_team_member(session, project.team_id, new_owner_user_id)
        try:
            await projects.get_by_id_for_update(session, project_id)
            old_owner = await project_members.get_owner(session, project_id, for_update=True)
            if old_owner is None:
                raise ProjectMemberNotFoundError("Project owner not found")
            if old_owner.user_id == new_owner_user_id:
                return old_owner
            new_owner = await project_members.get_by_project_and_user(
                session, project_id, new_owner_user_id
            )
            if new_owner is None:
                new_owner = ProjectMember(
                    project_id=project_id,
                    user_id=new_owner_user_id,
                    role=ProjectRole.MEMBER,
                )
                project_members.add(session, new_owner)
                await session.flush()
            old_owner.role = ProjectRole.MEMBER
            await session.flush()
            new_owner.role = ProjectRole.OWNER
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        return new_owner

    async def _require_manage(
        self, session: AsyncSession, current_user: User, project_id: UUID
    ) -> Project:
        project = await projects.get_by_id(session, project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found")
        if not await self.access.can_manage_project(session, current_user, project_id):
            raise ProjectAccessDeniedError("Project management permission required")
        return project

    @staticmethod
    async def _require_team_member(session: AsyncSession, team_id: UUID, user_id: UUID) -> None:
        if await users.get_by_id(session, user_id) is None:
            raise ProjectMemberNotFoundError("User not found")
        if await team_members.get_by_team_and_user(session, team_id, user_id) is None:
            raise ProjectMemberNotFoundError("User is not a member of the project team")

    @staticmethod
    def _validate_project_transition(current: ProjectStatus, target: ProjectStatus) -> None:
        if target not in PROJECT_TRANSITIONS[current]:
            raise InvalidStatusTransitionError(
                f"Project status cannot transition from {current.value} to {target.value}"
            )

    @staticmethod
    def _validate_dates(starts_at: datetime | None, due_at: datetime | None) -> None:
        if starts_at is not None and due_at is not None and due_at < starts_at:
            raise InvalidDeadlineError("due_at must not be before starts_at")

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


def get_project_service() -> ProjectService:
    return ProjectService()
