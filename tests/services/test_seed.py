from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from silly_teamwork.core.security import hash_invitation_code, verify_password
from silly_teamwork.db.base import Base
from silly_teamwork.db.session import get_db_session
from silly_teamwork.main import app
from silly_teamwork.models.enums import InvitationStatus, TeamRole
from silly_teamwork.models.invitation_code import InvitationCode
from silly_teamwork.models.system_admin import SystemAdmin
from silly_teamwork.models.team import Team
from silly_teamwork.models.team_member import TeamMember
from silly_teamwork.models.user import User
from silly_teamwork.services.seed import DevelopmentSeedService, SeedRequest

pytestmark = pytest.mark.asyncio

SEED_REQUEST = SeedRequest(
    admin_username="admin",
    admin_password="admin123456",
    admin_nickname="Administrator",
    team_name="Silly Teamwork Development Team",
    invite_code="ST-DEV-2026",
)


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield factory

    await engine.dispose()


async def test_seed_creates_admin_team_owner_and_hashed_invitation(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        result = await DevelopmentSeedService().run(session, SEED_REQUEST)

    assert result.admin_created is True
    assert result.team_created is True
    assert result.membership_created is True
    assert result.invitation_created is True
    assert result.system_admin_created is True
    assert result.invitation_status is InvitationStatus.ACTIVE

    async with session_factory() as session:
        admin = (await session.execute(select(User).where(User.username == "admin"))).scalar_one()
        assert admin.display_name == "Administrator"
        assert admin.email is None
        assert admin.is_superuser is False
        assert admin.password_hash != "admin123456"
        assert verify_password("admin123456", admin.password_hash)
        system_admin = (
            await session.execute(select(SystemAdmin).where(SystemAdmin.user_id == admin.id))
        ).scalar_one()
        assert system_admin.role.value == "super_admin"

        team = (
            await session.execute(
                select(Team).where(Team.name == "Silly Teamwork Development Team")
            )
        ).scalar_one()
        membership = (
            await session.execute(
                select(TeamMember).where(
                    TeamMember.team_id == team.id,
                    TeamMember.user_id == admin.id,
                )
            )
        ).scalar_one()
        assert membership.role is TeamRole.OWNER

        invitation = (
            await session.execute(
                select(InvitationCode).where(
                    InvitationCode.code_hash == hash_invitation_code("ST-DEV-2026")
                )
            )
        ).scalar_one()
        assert invitation.code_hash != "ST-DEV-2026"
        assert invitation.team_id == team.id
        assert invitation.created_by_id == admin.id
        assert invitation.role is TeamRole.MEMBER


async def test_seed_is_idempotent_and_does_not_reset_password(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = DevelopmentSeedService()
    async with session_factory() as session:
        first = await service.run(session, SEED_REQUEST)

    async with session_factory.begin() as session:
        admin = await session.get(User, first.admin_id)
        assert admin is not None
        original_hash = admin.password_hash

    async with session_factory() as session:
        second = await service.run(
            session,
            SeedRequest(
                admin_username="admin",
                admin_password="a-different-password",
                admin_nickname="Different name",
                team_name="Silly Teamwork Development Team",
                invite_code="ST-DEV-2026",
            ),
        )

    assert second.admin_id == first.admin_id
    assert second.team_id == first.team_id
    assert second.invitation_id == first.invitation_id
    assert second.admin_created is False
    assert second.team_created is False
    assert second.membership_created is False
    assert second.invitation_created is False
    assert second.system_admin_created is False

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User)) == 1
        assert await session.scalar(select(func.count()).select_from(Team)) == 1
        assert await session.scalar(select(func.count()).select_from(TeamMember)) == 1
        assert await session.scalar(select(func.count()).select_from(InvitationCode)) == 1
        assert await session.scalar(select(func.count()).select_from(SystemAdmin)) == 1
        admin = await session.get(User, first.admin_id)
        assert admin is not None
        assert admin.password_hash == original_hash
        assert verify_password("admin123456", admin.password_hash)


async def test_seed_data_supports_admin_login_and_invited_registration(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await DevelopmentSeedService().run(session, SEED_REQUEST)

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            login_response = await client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "admin123456"},
            )
            register_response = await client.post(
                "/api/v1/auth/register",
                json={
                    "username": "seeded_user",
                    "password": "seeded-user-password",
                    "nickname": "Seeded User",
                    "invite_code": "ST-DEV-2026",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert login_response.status_code == 200
    assert login_response.json()["access_token"]
    assert register_response.status_code == 201
    assert register_response.json()["username"] == "seeded_user"

    async with session_factory() as session:
        seeded_user = (
            await session.execute(select(User).where(User.username == "seeded_user"))
        ).scalar_one()
        membership = (
            await session.execute(select(TeamMember).where(TeamMember.user_id == seeded_user.id))
        ).scalar_one()
        assert membership.role is TeamRole.MEMBER
