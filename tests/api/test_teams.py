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
from silly_teamwork.models.enums import InvitationStatus, TeamRole
from silly_teamwork.models.invitation_code import InvitationCode
from silly_teamwork.models.team_member import TeamMember
from silly_teamwork.models.user import User

pytestmark = pytest.mark.asyncio


@dataclass(frozen=True)
class TeamTestContext:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]
    leader: User
    member: User
    outsider: User
    leader_headers: dict[str, str]
    member_headers: dict[str, str]
    outsider_headers: dict[str, str]


@pytest_asyncio.fixture
async def team_context() -> AsyncIterator[TeamTestContext]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with factory.begin() as session:
        leader = User(
            username="team_leader",
            display_name="Team Leader",
            password_hash=hash_password("leader-password"),
        )
        member = User(
            username="team_member",
            display_name="Team Member",
            password_hash=hash_password("member-password"),
        )
        outsider = User(
            username="team_outsider",
            display_name="Team Outsider",
            password_hash=hash_password("outsider-password"),
        )
        session.add_all([leader, member, outsider])
        await session.flush()

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield TeamTestContext(
            client=client,
            session_factory=factory,
            leader=leader,
            member=member,
            outsider=outsider,
            leader_headers=_auth_headers(leader.id),
            member_headers=_auth_headers(member.id),
            outsider_headers=_auth_headers(outsider.id),
        )

    app.dependency_overrides.clear()
    await engine.dispose()


def _auth_headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _create_team(context: TeamTestContext, name: str = "Database Group") -> dict[str, object]:
    response = await context.client.post(
        "/api/v1/teams",
        headers=context.leader_headers,
        json={
            "name": name,
            "description": "Semester group project",
            "course_name": "Database Systems",
        },
    )
    assert response.status_code == 201
    return response.json()


async def _create_invitation(
    context: TeamTestContext, team_id: str, role: str = "member"
) -> dict[str, object]:
    response = await context.client.post(
        f"/api/v1/teams/{team_id}/invite",
        headers=context.leader_headers,
        json={"role": role},
    )
    assert response.status_code == 201
    return response.json()


async def test_user_creates_team_and_automatically_becomes_leader(
    team_context: TeamTestContext,
) -> None:
    team = await _create_team(team_context)

    assert team["name"] == "Database Group"
    assert team["description"] == "Semester group project"
    assert team["course_name"] == "Database Systems"
    assert team["role"] == "leader"

    async with team_context.session_factory() as session:
        membership = (
            await session.execute(
                select(TeamMember).where(
                    TeamMember.team_id == UUID(str(team["id"])),
                    TeamMember.user_id == team_context.leader.id,
                )
            )
        ).scalar_one()
        assert membership.role is TeamRole.OWNER


async def test_leader_generates_hashed_invitation(team_context: TeamTestContext) -> None:
    team = await _create_team(team_context)
    invitation_response = await _create_invitation(team_context, str(team["id"]))

    plaintext = str(invitation_response["invite_code"])
    assert plaintext.startswith("ST-")
    assert invitation_response["role"] == "member"

    async with team_context.session_factory() as session:
        invitation = (
            await session.execute(
                select(InvitationCode).where(
                    InvitationCode.code_hash == hash_invitation_code(plaintext)
                )
            )
        ).scalar_one()
        assert invitation.code_hash != plaintext
        assert invitation.status is InvitationStatus.ACTIVE
        assert invitation.role is TeamRole.MEMBER


async def test_user_joins_team_and_team_detail_lists_members(
    team_context: TeamTestContext,
) -> None:
    team = await _create_team(team_context)
    invitation = await _create_invitation(team_context, str(team["id"]))

    join_response = await team_context.client.post(
        "/api/v1/teams/join",
        headers=team_context.member_headers,
        json={"invite_code": invitation["invite_code"]},
    )
    detail_response = await team_context.client.get(
        f"/api/v1/teams/{team['id']}", headers=team_context.member_headers
    )
    members_response = await team_context.client.get(
        f"/api/v1/teams/{team['id']}/members", headers=team_context.member_headers
    )

    assert join_response.status_code == 200
    assert join_response.json()["role"] == "member"
    assert detail_response.status_code == 200
    assert detail_response.json()["role"] == "member"
    assert {item["username"]: item["role"] for item in detail_response.json()["members"]} == {
        "team_leader": "leader",
        "team_member": "member",
    }
    assert members_response.status_code == 200
    assert {item["username"] for item in members_response.json()} == {
        "team_leader",
        "team_member",
    }

    async with team_context.session_factory() as session:
        stored_invitation = (
            await session.execute(
                select(InvitationCode).where(
                    InvitationCode.code_hash == hash_invitation_code(str(invitation["invite_code"]))
                )
            )
        ).scalar_one()
        assert stored_invitation.status is InvitationStatus.USED
        assert stored_invitation.used_by_id == team_context.member.id


async def test_regular_member_cannot_generate_invitation(
    team_context: TeamTestContext,
) -> None:
    team = await _create_team(team_context)
    invitation = await _create_invitation(team_context, str(team["id"]))
    await team_context.client.post(
        "/api/v1/teams/join",
        headers=team_context.member_headers,
        json={"invite_code": invitation["invite_code"]},
    )

    response = await team_context.client.post(
        f"/api/v1/teams/{team['id']}/invite",
        headers=team_context.member_headers,
        json={"role": "member"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Only the team leader can create invitations"


async def test_user_can_belong_to_multiple_teams(team_context: TeamTestContext) -> None:
    first_team = await _create_team(team_context, "Database Group")
    second_team = await _create_team(team_context, "Software Engineering Group")
    first_invitation = await _create_invitation(team_context, str(first_team["id"]))
    second_invitation = await _create_invitation(team_context, str(second_team["id"]), "leader")

    for invitation in (first_invitation, second_invitation):
        response = await team_context.client.post(
            "/api/v1/teams/join",
            headers=team_context.outsider_headers,
            json={"invite_code": invitation["invite_code"]},
        )
        assert response.status_code == 200

    my_teams_response = await team_context.client.get(
        "/api/v1/teams", headers=team_context.outsider_headers
    )

    assert my_teams_response.status_code == 200
    teams_by_name = {item["name"]: item["role"] for item in my_teams_response.json()}
    assert teams_by_name == {
        "Database Group": "member",
        "Software Engineering Group": "leader",
    }


async def test_non_member_cannot_view_team(team_context: TeamTestContext) -> None:
    team = await _create_team(team_context)

    detail_response = await team_context.client.get(
        f"/api/v1/teams/{team['id']}", headers=team_context.outsider_headers
    )
    members_response = await team_context.client.get(
        f"/api/v1/teams/{team['id']}/members", headers=team_context.outsider_headers
    )

    assert detail_response.status_code == 404
    assert members_response.status_code == 404


async def test_openapi_documents_team_contract(team_context: TeamTestContext) -> None:
    response = await team_context.client.get("/openapi.json")
    schema = response.json()

    expected_operations = {
        "/api/v1/teams": {"get", "post"},
        "/api/v1/teams/join": {"post"},
        "/api/v1/teams/{team_id}": {"get"},
        "/api/v1/teams/{team_id}/invite": {"post"},
        "/api/v1/teams/{team_id}/members": {"get"},
    }
    for path, methods in expected_operations.items():
        assert methods.issubset(schema["paths"][path])
    assert schema["paths"]["/api/v1/teams"]["post"]["security"] == [{"HTTPBearer": []}]
