from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.core.security import hash_invitation_code
from silly_teamwork.models.enums import InvitationStatus, TeamRole
from silly_teamwork.models.invitation_code import InvitationCode
from silly_teamwork.models.team import Team
from silly_teamwork.models.team_member import TeamMember
from silly_teamwork.models.user import User
from silly_teamwork.repositories import files, invitation_codes, team_members, teams
from silly_teamwork.schemas.team import InvitationCreateRequest, InvitationRole, TeamCreateRequest
from silly_teamwork.services.collaboration_access import CollaborationAccessService
from silly_teamwork.services.exceptions import (
    AlreadyTeamMemberError,
    InvalidInvitationError,
    TeamAccessDeniedError,
    TeamNotFoundError,
)
from silly_teamwork.services.file_cleanup import FileCleanupService


@dataclass(frozen=True, slots=True)
class TeamWithRole:
    team: Team
    role: TeamRole


@dataclass(frozen=True, slots=True)
class TeamMemberWithUser:
    membership: TeamMember
    user: User


@dataclass(frozen=True, slots=True)
class CreatedInvitation:
    invitation: InvitationCode
    plaintext_code: str
    public_role: InvitationRole


class TeamService:
    def __init__(
        self,
        access_service: CollaborationAccessService | None = None,
        cleanup_service: FileCleanupService | None = None,
    ) -> None:
        self.access = access_service or CollaborationAccessService()
        self.cleanup = cleanup_service or FileCleanupService()

    async def create_team(
        self, session: AsyncSession, current_user: User, payload: TeamCreateRequest
    ) -> TeamWithRole:
        try:
            team = Team(
                name=payload.name,
                description=self._optional_text(payload.description),
                course_name=self._optional_text(payload.course_name),
                created_by_id=current_user.id,
            )
            teams.add(session, team)
            await session.flush()

            membership = TeamMember(
                team_id=team.id,
                user_id=current_user.id,
                role=TeamRole.OWNER,
            )
            team_members.add(session, membership)
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        return TeamWithRole(team=team, role=membership.role)

    async def list_my_teams(self, session: AsyncSession, current_user: User) -> list[TeamWithRole]:
        rows = await teams.list_for_user(session, current_user.id)
        return [TeamWithRole(team=team, role=membership.role) for team, membership in rows]

    async def get_team_detail(
        self, session: AsyncSession, current_user: User, team_id: UUID
    ) -> tuple[TeamWithRole, list[TeamMemberWithUser]]:
        team, membership = await self._require_membership(session, team_id, current_user.id)
        members = await team_members.list_with_users_for_team(session, team_id)
        return TeamWithRole(team=team, role=membership.role), [
            TeamMemberWithUser(membership=item, user=user) for item, user in members
        ]

    async def delete_team(
        self, session: AsyncSession, current_user: User, team_id: UUID
    ) -> None:
        team = await teams.get_by_id(session, team_id)
        if team is None:
            raise TeamNotFoundError("Team not found")
        if not await self.access.can_delete_team(session, current_user, team_id):
            raise TeamAccessDeniedError("Team deletion permission required")

        team_files = await files.list_all_for_team(session, team_id)
        cleanup_batch = await self.cleanup.stage(file.storage_key for file in team_files)
        try:
            await teams.delete(session, team)
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            await self.cleanup.restore(cleanup_batch)
            raise
        await self.cleanup.finish(cleanup_batch)

    async def list_members(
        self, session: AsyncSession, current_user: User, team_id: UUID
    ) -> list[TeamMemberWithUser]:
        await self._require_membership(session, team_id, current_user.id)
        members = await team_members.list_with_users_for_team(session, team_id)
        return [TeamMemberWithUser(membership=item, user=user) for item, user in members]

    async def create_invitation(
        self,
        session: AsyncSession,
        current_user: User,
        team_id: UUID,
        payload: InvitationCreateRequest,
    ) -> CreatedInvitation:
        try:
            _, membership = await self._require_membership(session, team_id, current_user.id)
            if membership.role is not TeamRole.OWNER:
                raise TeamAccessDeniedError("Only the team leader can create invitations")

            plaintext_code = await self._new_unique_invitation_code(session)
            invitation = InvitationCode(
                code_hash=hash_invitation_code(plaintext_code),
                team_id=team_id,
                created_by_id=current_user.id,
                role=payload.role.to_model(),
                status=InvitationStatus.ACTIVE,
            )
            invitation_codes.add(session, invitation)
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            raise

        return CreatedInvitation(
            invitation=invitation,
            plaintext_code=plaintext_code,
            public_role=payload.role,
        )

    async def join_team(
        self, session: AsyncSession, current_user: User, invite_code: str
    ) -> TeamWithRole:
        code_hash = hash_invitation_code(invite_code)
        try:
            invitation = await invitation_codes.get_by_hash_for_update(session, code_hash)
            invitation = self._validate_invitation(invitation)
            if invitation.team_id is None:
                raise InvalidInvitationError("Invitation code is not linked to a team")

            team = await teams.get_by_id(session, invitation.team_id)
            if team is None:
                raise InvalidInvitationError("Invitation code is invalid or expired")

            existing = await team_members.get_by_team_and_user(
                session, invitation.team_id, current_user.id
            )
            if existing is not None:
                raise AlreadyTeamMemberError("User is already a member of this team")

            membership = TeamMember(
                team_id=invitation.team_id,
                user_id=current_user.id,
                role=invitation.role,
            )
            team_members.add(session, membership)
            invitation.status = InvitationStatus.USED
            invitation.used_by_id = current_user.id
            invitation.used_at = datetime.now(UTC)
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        return TeamWithRole(team=team, role=membership.role)

    async def _require_membership(
        self, session: AsyncSession, team_id: UUID, user_id: UUID
    ) -> tuple[Team, TeamMember]:
        team = await teams.get_by_id(session, team_id)
        if team is None:
            raise TeamNotFoundError("Team not found")
        membership = await team_members.get_by_team_and_user(session, team_id, user_id)
        if membership is None:
            raise TeamNotFoundError("Team not found")
        return team, membership

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @staticmethod
    async def _new_unique_invitation_code(session: AsyncSession) -> str:
        for _ in range(5):
            plaintext = f"ST-{secrets.token_urlsafe(18)}"
            existing = await invitation_codes.get_by_hash(session, hash_invitation_code(plaintext))
            if existing is None:
                return plaintext
        raise RuntimeError("Could not generate a unique invitation code")

    @staticmethod
    def _validate_invitation(invitation: InvitationCode | None) -> InvitationCode:
        now = datetime.now(UTC)
        is_expired = invitation is not None and (
            invitation.expires_at is not None and invitation.expires_at <= now
        )
        if (
            invitation is None
            or invitation.status is not InvitationStatus.ACTIVE
            or invitation.used_by_id is not None
            or is_expired
        ):
            raise InvalidInvitationError("Invitation code is invalid or expired")
        return invitation


def get_team_service() -> TeamService:
    return TeamService()
