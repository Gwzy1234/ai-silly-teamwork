from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from silly_teamwork.core.security import hash_password, verify_password
from silly_teamwork.db.base import Base
from silly_teamwork.db.session import get_db_session
from silly_teamwork.main import app
from silly_teamwork.models.enums import InvitationStatus, TeamRole
from silly_teamwork.models.invitation_code import InvitationCode
from silly_teamwork.models.team import Team
from silly_teamwork.models.team_member import TeamMember
from silly_teamwork.models.user import User
from silly_teamwork.services.auth import AuthService

pytestmark = pytest.mark.asyncio

VALID_INVITE_CODE = "STW-TEST-INVITE"
REGISTER_PAYLOAD = {
    "username": "alice_chen",
    "password": "correct-horse-battery-staple",
    "nickname": "Alice",
    "email": "alice@example.edu",
    "invite_code": VALID_INVITE_CODE,
}


@dataclass(frozen=True)
class AuthTestContext:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]
    team_id: UUID


@pytest_asyncio.fixture
async def auth_context() -> AsyncIterator[AuthTestContext]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory.begin() as session:
        inviter = User(
            username="inviter",
            email="inviter@example.edu",
            display_name="Inviter",
            password_hash=hash_password("inviter-password"),
        )
        session.add(inviter)
        await session.flush()

        team = Team(name="Software Engineering Group", created_by_id=inviter.id)
        session.add(team)
        await session.flush()

        session.add(
            InvitationCode(
                code_hash=AuthService.hash_invite_code(VALID_INVITE_CODE),
                team_id=team.id,
                created_by_id=inviter.id,
                role=TeamRole.MEMBER,
            )
        )

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield AuthTestContext(client=client, session_factory=session_factory, team_id=team.id)

    app.dependency_overrides.clear()
    await engine.dispose()


async def test_register_login_and_get_current_user(auth_context: AuthTestContext) -> None:
    register_response = await auth_context.client.post(
        "/api/v1/auth/register", json=REGISTER_PAYLOAD
    )

    assert register_response.status_code == 201
    registered_user = register_response.json()
    assert registered_user["username"] == "alice_chen"
    assert registered_user["nickname"] == "Alice"
    assert registered_user["email"] == "alice@example.edu"
    assert "password" not in registered_user
    assert "password_hash" not in registered_user

    user_id = UUID(registered_user["id"])
    async with auth_context.session_factory() as session:
        user = await session.get(User, user_id)
        assert user is not None
        assert user.password_hash != REGISTER_PAYLOAD["password"]
        assert verify_password(REGISTER_PAYLOAD["password"], user.password_hash)

        invitation = (
            await session.execute(
                select(InvitationCode).where(
                    InvitationCode.code_hash == AuthService.hash_invite_code(VALID_INVITE_CODE)
                )
            )
        ).scalar_one()
        assert invitation.status is InvitationStatus.USED
        assert invitation.used_by_id == user_id

        membership = (
            await session.execute(
                select(TeamMember).where(
                    TeamMember.team_id == auth_context.team_id,
                    TeamMember.user_id == user_id,
                )
            )
        ).scalar_one()
        assert membership.role is TeamRole.MEMBER

    login_response = await auth_context.client.post(
        "/api/v1/auth/login",
        json={"username": REGISTER_PAYLOAD["username"], "password": REGISTER_PAYLOAD["password"]},
    )

    assert login_response.status_code == 200
    token = login_response.json()
    assert token["token_type"] == "bearer"
    assert token["access_token"]
    assert token["expires_in"] > 0

    me_response = await auth_context.client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json() == registered_user


async def test_register_rejects_invalid_invitation(auth_context: AuthTestContext) -> None:
    response = await auth_context.client.post(
        "/api/v1/auth/register", json={**REGISTER_PAYLOAD, "invite_code": "wrong-code"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invitation code is invalid or expired"


async def test_register_succeeds_without_optional_email(auth_context: AuthTestContext) -> None:
    response = await auth_context.client.post(
        "/api/v1/auth/register",
        json={key: value for key, value in REGISTER_PAYLOAD.items() if key != "email"},
    )

    assert response.status_code == 201
    assert response.json()["email"] is None

    user_id = UUID(response.json()["id"])
    async with auth_context.session_factory() as session:
        user = await session.get(User, user_id)
        assert user is not None
        assert user.email is None


async def test_register_rejects_duplicate_user(auth_context: AuthTestContext) -> None:
    first_response = await auth_context.client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    second_invite_code = "STW-SECOND-INVITE"
    async with auth_context.session_factory.begin() as session:
        inviter = (
            await session.execute(select(User).where(User.username == "inviter"))
        ).scalar_one()
        session.add(
            InvitationCode(
                code_hash=AuthService.hash_invite_code(second_invite_code),
                team_id=auth_context.team_id,
                created_by_id=inviter.id,
                role=TeamRole.MEMBER,
            )
        )

    second_response = await auth_context.client.post(
        "/api/v1/auth/register",
        json={
            **REGISTER_PAYLOAD,
            "email": "another@example.edu",
            "invite_code": second_invite_code,
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Username is already registered"


async def test_login_rejects_wrong_password(auth_context: AuthTestContext) -> None:
    await auth_context.client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    response = await auth_context.client.post(
        "/api/v1/auth/login",
        json={"username": REGISTER_PAYLOAD["username"], "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["detail"] == "Invalid username or password"


async def test_get_me_requires_a_valid_bearer_token(auth_context: AuthTestContext) -> None:
    missing_response = await auth_context.client.get("/api/v1/users/me")
    invalid_response = await auth_context.client.get(
        "/api/v1/users/me", headers={"Authorization": "Bearer not-a-jwt"}
    )

    assert missing_response.status_code == 401
    assert invalid_response.status_code == 401


async def test_openapi_documents_authentication_contract(auth_context: AuthTestContext) -> None:
    response = await auth_context.client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "/api/v1/auth/register" in schema["paths"]
    assert "/api/v1/auth/login" in schema["paths"]
    assert "/api/v1/users/me" in schema["paths"]
    assert schema["paths"]["/api/v1/users/me"]["get"]["security"] == [{"HTTPBearer": []}]
    assert "RegisterRequest" in schema["components"]["schemas"]
    assert "TokenResponse" in schema["components"]["schemas"]
    assert "UserResponse" in schema["components"]["schemas"]
