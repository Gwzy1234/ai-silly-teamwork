from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.team import Team
from silly_teamwork.models.team_member import TeamMember


async def get_by_name_and_creator(
    session: AsyncSession, name: str, created_by_id: UUID
) -> Team | None:
    result = await session.execute(
        select(Team).where(Team.name == name, Team.created_by_id == created_by_id)
    )
    return result.scalar_one_or_none()


def add(session: AsyncSession, team: Team) -> None:
    session.add(team)


async def delete(session: AsyncSession, team: Team) -> None:
    await session.delete(team)


async def get_by_id(session: AsyncSession, team_id: UUID) -> Team | None:
    return await session.get(Team, team_id)


async def list_for_user(session: AsyncSession, user_id: UUID) -> list[tuple[Team, TeamMember]]:
    result = await session.execute(
        select(Team, TeamMember)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(TeamMember.user_id == user_id)
        .order_by(Team.created_at.desc(), Team.name)
    )
    return list(result.tuples().all())


async def list_all(session: AsyncSession) -> list[Team]:
    result = await session.execute(select(Team).order_by(Team.created_at, Team.name))
    return list(result.scalars().all())
