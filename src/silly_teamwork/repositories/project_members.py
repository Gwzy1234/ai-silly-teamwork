from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.enums import ProjectRole
from silly_teamwork.models.project_member import ProjectMember


def add(session: AsyncSession, membership: ProjectMember) -> None:
    session.add(membership)


async def get_by_project_and_user(
    session: AsyncSession, project_id: UUID, user_id: UUID
) -> ProjectMember | None:
    result = await session.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_owner(
    session: AsyncSession, project_id: UUID, *, for_update: bool = False
) -> ProjectMember | None:
    statement = select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.role == ProjectRole.OWNER,
    )
    if for_update:
        statement = statement.with_for_update()
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def list_for_project(session: AsyncSession, project_id: UUID) -> list[ProjectMember]:
    result = await session.execute(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.joined_at, ProjectMember.id)
    )
    return list(result.scalars().all())


async def delete(session: AsyncSession, membership: ProjectMember) -> None:
    await session.delete(membership)


async def list_project_ids_for_user(session: AsyncSession, user_id: UUID) -> set[UUID]:
    result = await session.execute(
        select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)
    )
    return set(result.scalars().all())
