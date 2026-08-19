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

from silly_teamwork.core.security import create_access_token, hash_invitation_code, hash_password
from silly_teamwork.db.base import Base
from silly_teamwork.db.session import get_db_session
from silly_teamwork.main import app
from silly_teamwork.models.enums import InvitationStatus, SystemAdminRole, TeamRole
from silly_teamwork.models.invitation_code import InvitationCode
from silly_teamwork.models.system_admin import SystemAdmin
from silly_teamwork.models.team import Team
from silly_teamwork.models.team_member import TeamMember
from silly_teamwork.models.user import User

pytestmark = pytest.mark.asyncio


@dataclass(frozen=True)
class AdminTestContext:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]
    system_admin: User
    leader: User
    member: User
    team: Team
    admin_headers: dict[str, str]
    leader_headers: dict[str, str]
    member_headers: dict[str, str]


@pytest_asyncio.fixture
async def admin_context() -> AsyncIterator[AdminTestContext]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with factory.begin() as session:
        system_admin = User(
            username="system_admin",
            display_name="System Admin",
            password_hash=hash_password("system-admin-password"),
        )
        leader = User(
            username="course_leader",
            display_name="Course Leader",
            password_hash=hash_password("leader-password"),
        )
        member = User(
            username="course_member",
            display_name="Course Member",
            password_hash=hash_password("member-password"),
        )
        session.add_all([system_admin, leader, member])
        await session.flush()

        session.add(SystemAdmin(user_id=system_admin.id, role=SystemAdminRole.SUPER_ADMIN))
        team = Team(name="Operating Systems Group", created_by_id=leader.id)
        session.add(team)
        await session.flush()
        session.add_all(
            [
                TeamMember(team_id=team.id, user_id=leader.id, role=TeamRole.OWNER),
                TeamMember(team_id=team.id, user_id=member.id, role=TeamRole.MEMBER),
            ]
        )

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield AdminTestContext(
            client=client,
            session_factory=factory,
            system_admin=system_admin,
            leader=leader,
            member=member,
            team=team,
            admin_headers=_auth_headers(system_admin.id),
            leader_headers=_auth_headers(leader.id),
            member_headers=_auth_headers(member.id),
        )

    app.dependency_overrides.clear()
    await engine.dispose()


def _auth_headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def test_super_admin_can_list_users_and_teams(
    admin_context: AdminTestContext,
) -> None:
    users_response = await admin_context.client.get(
        "/api/v1/admin/users", headers=admin_context.admin_headers
    )
    teams_response = await admin_context.client.get(
        "/api/v1/admin/teams", headers=admin_context.admin_headers
    )

    assert users_response.status_code == 200
    assert {user["username"] for user in users_response.json()} == {
        "system_admin",
        "course_leader",
        "course_member",
    }
    assert teams_response.status_code == 200
    assert teams_response.json()[0]["name"] == "Operating Systems Group"


@pytest.mark.parametrize("headers_name", ["member_headers", "leader_headers"])
async def test_non_system_admin_and_team_leader_receive_403(
    admin_context: AdminTestContext, headers_name: str
) -> None:
    response = await admin_context.client.get(
        "/api/v1/admin/users", headers=getattr(admin_context, headers_name)
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "System administrator access required"


async def test_banned_user_cannot_login_and_unban_restores_login(
    admin_context: AdminTestContext,
) -> None:
    ban_response = await admin_context.client.post(
        f"/api/v1/admin/users/{admin_context.member.id}/ban",
        headers=admin_context.admin_headers,
    )
    banned_login = await admin_context.client.post(
        "/api/v1/auth/login",
        json={"username": "course_member", "password": "member-password"},
    )
    unban_response = await admin_context.client.post(
        f"/api/v1/admin/users/{admin_context.member.id}/unban",
        headers=admin_context.admin_headers,
    )
    restored_login = await admin_context.client.post(
        "/api/v1/auth/login",
        json={"username": "course_member", "password": "member-password"},
    )

    assert ban_response.status_code == 200
    assert banned_login.status_code == 401
    assert unban_response.status_code == 200
    assert restored_login.status_code == 200
    assert restored_login.json()["access_token"]


async def test_super_admin_removes_team_member_without_deleting_user(
    admin_context: AdminTestContext,
) -> None:
    response = await admin_context.client.delete(
        f"/api/v1/admin/teams/{admin_context.team.id}/members/{admin_context.member.id}",
        headers=admin_context.admin_headers,
    )

    assert response.status_code == 200
    async with admin_context.session_factory() as session:
        membership = (
            await session.execute(
                select(TeamMember).where(
                    TeamMember.team_id == admin_context.team.id,
                    TeamMember.user_id == admin_context.member.id,
                )
            )
        ).scalar_one_or_none()
        assert membership is None
        assert await session.get(User, admin_context.member.id) is not None


async def test_super_admin_generates_hashed_global_invitation(
    admin_context: AdminTestContext,
) -> None:
    response = await admin_context.client.post(
        "/api/v1/admin/invites", headers=admin_context.admin_headers
    )

    assert response.status_code == 201
    plaintext = response.json()["invite_code"]
    assert plaintext.startswith("ST-GLOBAL-")
    async with admin_context.session_factory() as session:
        invitation = (
            await session.execute(
                select(InvitationCode).where(
                    InvitationCode.code_hash == hash_invitation_code(plaintext)
                )
            )
        ).scalar_one()
        assert invitation.code_hash != plaintext
        assert invitation.team_id is None
        assert invitation.status is InvitationStatus.ACTIVE


async def test_admin_openapi_contract(admin_context: AdminTestContext) -> None:
    response = await admin_context.client.get("/openapi.json")
    paths = response.json()["paths"]
    expected = {
        "/api/v1/admin/users": "get",
        "/api/v1/admin/users/{user_id}/ban": "post",
        "/api/v1/admin/users/{user_id}/unban": "post",
        "/api/v1/admin/teams/{team_id}/members/{user_id}": "delete",
        "/api/v1/admin/invites": "post",
        "/api/v1/admin/teams": "get",
    }
    for path, method in expected.items():
        assert paths[path][method]["security"] == [{"HTTPBearer": []}]
