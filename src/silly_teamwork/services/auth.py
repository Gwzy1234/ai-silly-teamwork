from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.core.config import get_settings
from silly_teamwork.core.security import (
    create_access_token,
    hash_invitation_code,
    hash_password,
    verify_password,
)
from silly_teamwork.models.enums import InvitationStatus
from silly_teamwork.models.invitation_code import InvitationCode
from silly_teamwork.models.team_member import TeamMember
from silly_teamwork.models.user import User
from silly_teamwork.repositories import invitation_codes, team_members, users
from silly_teamwork.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from silly_teamwork.services.exceptions import (
    InvalidCredentialsError,
    InvalidInvitationError,
    RegistrationConflictError,
)

# Keeps missing-user and wrong-password login paths closer in computational cost.
_DUMMY_PASSWORD_HASH = hash_password("silly-teamwork-dummy-password")


class AuthService:
    async def register(self, session: AsyncSession, payload: RegisterRequest) -> User:
        username = payload.username.strip().lower()
        email = str(payload.email).strip().lower() if payload.email is not None else None
        nickname = payload.nickname.strip()
        invite_hash = self.hash_invite_code(payload.invite_code.get_secret_value())

        try:
            async with session.begin():
                invitation = await invitation_codes.get_by_hash_for_update(session, invite_hash)
                invitation = self._validate_invitation(invitation)

                if await users.get_by_username(session, username) is not None:
                    raise RegistrationConflictError("Username is already registered")
                if email is not None and await users.get_by_email(session, email) is not None:
                    raise RegistrationConflictError("Email is already registered")

                user = User(
                    username=username,
                    email=email,
                    display_name=nickname,
                    password_hash=hash_password(payload.password.get_secret_value()),
                )
                users.add(session, user)
                await session.flush()

                if invitation.team_id is not None:
                    team_members.add(
                        session,
                        TeamMember(
                            team_id=invitation.team_id, user_id=user.id, role=invitation.role
                        ),
                    )

                invitation.status = InvitationStatus.USED
                invitation.used_by_id = user.id
                invitation.used_at = datetime.now(UTC)
                await session.flush()
        except IntegrityError as error:
            raise RegistrationConflictError("Username or email is already registered") from error

        await session.refresh(user)
        return user

    async def login(self, session: AsyncSession, payload: LoginRequest) -> TokenResponse:
        username = payload.username.strip().lower()
        user = await users.get_by_username(session, username)
        password = payload.password.get_secret_value()

        if user is None:
            verify_password(password, _DUMMY_PASSWORD_HASH)
            raise InvalidCredentialsError("Invalid username or password")

        if not verify_password(password, user.password_hash) or not user.is_active:
            raise InvalidCredentialsError("Invalid username or password")

        settings = get_settings()
        return TokenResponse(
            access_token=create_access_token(str(user.id)),
            expires_in=settings.access_token_expire_minutes * 60,
        )

    @staticmethod
    def hash_invite_code(invite_code: str) -> str:
        return hash_invitation_code(invite_code)

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


def get_auth_service() -> AuthService:
    return AuthService()
