from __future__ import annotations

import secrets
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.core.security import hash_invitation_code
from silly_teamwork.models.enums import InvitationStatus, TeamRole
from silly_teamwork.models.invitation_code import InvitationCode
from silly_teamwork.models.team import Team
from silly_teamwork.models.user import User
from silly_teamwork.repositories import invitation_codes, team_members, teams, users
from silly_teamwork.services.exceptions import AdminTargetNotFoundError


@dataclass(frozen=True, slots=True)
class CreatedGlobalInvitation:
    invitation: InvitationCode
    plaintext_code: str


class AdminService:
    async def list_users(self, session: AsyncSession) -> list[User]:
        return await users.list_all(session)

    async def set_user_active(
        self, session: AsyncSession, user_id: UUID, *, is_active: bool
    ) -> User:
        user = await users.get_by_id(session, user_id)
        if user is None:
            raise AdminTargetNotFoundError("User not found")
        try:
            user.is_active = is_active
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        return user

    async def remove_team_member(self, session: AsyncSession, team_id: UUID, user_id: UUID) -> None:
        if await teams.get_by_id(session, team_id) is None:
            raise AdminTargetNotFoundError("Team not found")
        try:
            deleted = await team_members.delete_by_team_and_user(session, team_id, user_id)
            if not deleted:
                raise AdminTargetNotFoundError("Team membership not found")
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    async def create_global_invitation(
        self, session: AsyncSession, current_user: User
    ) -> CreatedGlobalInvitation:
        plaintext = await self._new_unique_invitation_code(session)
        invitation = InvitationCode(
            code_hash=hash_invitation_code(plaintext),
            team_id=None,
            created_by_id=current_user.id,
            role=TeamRole.MEMBER,
            status=InvitationStatus.ACTIVE,
        )
        try:
            invitation_codes.add(session, invitation)
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        return CreatedGlobalInvitation(invitation=invitation, plaintext_code=plaintext)

    async def list_teams(self, session: AsyncSession) -> list[Team]:
        return await teams.list_all(session)

    @staticmethod
    async def _new_unique_invitation_code(session: AsyncSession) -> str:
        for _ in range(5):
            plaintext = f"ST-GLOBAL-{secrets.token_urlsafe(18)}"
            if await invitation_codes.get_by_hash(session, hash_invitation_code(plaintext)) is None:
                return plaintext
        raise RuntimeError("Could not generate a unique invitation code")


def get_admin_service() -> AdminService:
    return AdminService()
