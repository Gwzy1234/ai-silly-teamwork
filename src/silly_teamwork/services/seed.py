from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.core.security import hash_invitation_code, hash_password
from silly_teamwork.models.enums import InvitationStatus, SystemAdminRole, TeamRole
from silly_teamwork.models.invitation_code import InvitationCode
from silly_teamwork.models.system_admin import SystemAdmin
from silly_teamwork.models.team import Team
from silly_teamwork.models.team_member import TeamMember
from silly_teamwork.models.user import User
from silly_teamwork.repositories import (
    invitation_codes,
    system_admins,
    team_members,
    teams,
    users,
)


@dataclass(frozen=True, slots=True)
class SeedRequest:
    admin_username: str
    admin_password: str
    admin_nickname: str
    team_name: str
    invite_code: str


@dataclass(frozen=True, slots=True)
class SeedResult:
    admin_id: UUID
    team_id: UUID
    invitation_id: UUID
    invitation_status: InvitationStatus
    admin_created: bool
    team_created: bool
    membership_created: bool
    invitation_created: bool
    system_admin_created: bool


class DevelopmentSeedService:
    """Idempotently create the minimum data needed for local development."""

    async def run(self, session: AsyncSession, request: SeedRequest) -> SeedResult:
        username = request.admin_username.strip().lower()
        nickname = request.admin_nickname.strip()
        team_name = request.team_name.strip()
        code_hash = hash_invitation_code(request.invite_code)

        async with session.begin():
            admin = await users.get_by_username(session, username)
            admin_created = admin is None
            if admin is None:
                admin = User(
                    username=username,
                    email=None,
                    display_name=nickname,
                    password_hash=hash_password(request.admin_password),
                    is_superuser=False,
                )
                users.add(session, admin)
                await session.flush()

            system_admin = await system_admins.get_by_user_id(session, admin.id)
            system_admin_created = system_admin is None
            if system_admin is None:
                system_admins.add(
                    session,
                    SystemAdmin(user_id=admin.id, role=SystemAdminRole.SUPER_ADMIN),
                )

            team = await teams.get_by_name_and_creator(session, team_name, admin.id)
            team_created = team is None
            if team is None:
                team = Team(
                    name=team_name,
                    description="Default team created by the development seed.",
                    created_by_id=admin.id,
                )
                teams.add(session, team)
                await session.flush()

            membership = await team_members.get_by_team_and_user(session, team.id, admin.id)
            membership_created = membership is None
            if membership is None:
                membership = TeamMember(
                    team_id=team.id,
                    user_id=admin.id,
                    role=TeamRole.OWNER,
                )
                team_members.add(session, membership)
            elif membership.role is not TeamRole.OWNER:
                membership.role = TeamRole.OWNER

            invitation = await invitation_codes.get_by_hash(session, code_hash)
            invitation_created = invitation is None
            if invitation is None:
                invitation = InvitationCode(
                    code_hash=code_hash,
                    team_id=team.id,
                    created_by_id=admin.id,
                    role=TeamRole.MEMBER,
                    status=InvitationStatus.ACTIVE,
                )
                invitation_codes.add(session, invitation)

            await session.flush()

            return SeedResult(
                admin_id=admin.id,
                team_id=team.id,
                invitation_id=invitation.id,
                invitation_status=invitation.status,
                admin_created=admin_created,
                team_created=team_created,
                membership_created=membership_created,
                invitation_created=invitation_created,
                system_admin_created=system_admin_created,
            )
