from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.enums import TeamRole
from silly_teamwork.models.team_member import TeamMember
from silly_teamwork.models.user import User


def add(session: AsyncSession, membership: TeamMember) -> None:
    session.add(membership)


async def get_by_team_and_user(
    session: AsyncSession, team_id: UUID, user_id: UUID
) -> TeamMember | None:
    result = await session.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def list_with_users_for_team(
    session: AsyncSession, team_id: UUID
) -> list[tuple[TeamMember, User]]:
    result = await session.execute(
        select(TeamMember, User)
        .join(User, User.id == TeamMember.user_id)
        .where(TeamMember.team_id == team_id)
        .order_by(TeamMember.joined_at, User.username)
    )
    return list(result.tuples().all())


async def delete_by_team_and_user(session: AsyncSession, team_id: UUID, user_id: UUID) -> bool:
    membership = await get_by_team_and_user(session, team_id, user_id)
    if membership is None:
        return False
    await session.delete(membership)
    return True


async def list_leader_team_ids(session: AsyncSession, user_id: UUID) -> set[UUID]:
    result = await session.execute(
        select(TeamMember.team_id).where(
            TeamMember.user_id == user_id,
            TeamMember.role == TeamRole.OWNER,
        )
    )
    return set(result.scalars().all())


async def list_existing_user_ids(
    session: AsyncSession, team_id: UUID, user_ids: list[UUID]
) -> set[UUID]:
    if not user_ids:
        return set()
    result = await session.execute(
        select(TeamMember.user_id).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id.in_(user_ids),
        )
    )
    return set(result.scalars().all())
