from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.project import Project
from silly_teamwork.models.project_member import ProjectMember


def add(session: AsyncSession, project: Project) -> None:
    session.add(project)


async def delete(session: AsyncSession, project: Project) -> None:
    await session.delete(project)


async def get_by_id(session: AsyncSession, project_id: UUID) -> Project | None:
    return await session.get(Project, project_id)


async def get_by_id_for_update(session: AsyncSession, project_id: UUID) -> Project | None:
    result = await session.execute(
        select(Project).where(Project.id == project_id).with_for_update()
    )
    return result.scalar_one_or_none()


async def list_for_team(session: AsyncSession, team_id: UUID) -> list[Project]:
    result = await session.execute(
        select(Project)
        .where(Project.team_id == team_id)
        .order_by(Project.created_at.desc(), Project.name)
    )
    return list(result.scalars().all())


async def list_for_user_in_team(
    session: AsyncSession, team_id: UUID, user_id: UUID
) -> list[Project]:
    result = await session.execute(
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(Project.team_id == team_id, ProjectMember.user_id == user_id)
        .order_by(Project.created_at.desc(), Project.name)
    )
    return list(result.scalars().all())
