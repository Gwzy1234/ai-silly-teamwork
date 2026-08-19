from typing import cast
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Select

from silly_teamwork.models.enums import TaskType
from silly_teamwork.models.file import File
from silly_teamwork.models.project import Project
from silly_teamwork.models.task import Task
from silly_teamwork.models.team import Team
from silly_teamwork.models.user import User

FileIndexRow = tuple[File, Project, Task | None, Team, User | None]


def create_file(session: AsyncSession, file: File) -> None:
    session.add(file)


async def get_file(session: AsyncSession, file_id: UUID) -> File | None:
    return await session.get(File, file_id)


async def get_by_id(session: AsyncSession, file_id: UUID) -> File | None:
    """Compatibility alias used by the collaboration access service."""

    return await get_file(session, file_id)


async def list_project_files(session: AsyncSession, project_id: UUID) -> list[File]:
    result = await session.execute(
        select(File)
        .where(File.project_id == project_id)
        .order_by(File.created_at.desc(), File.original_name)
    )
    return list(result.scalars().all())


async def list_task_files(session: AsyncSession, task_id: UUID) -> list[File]:
    result = await session.execute(
        select(File)
        .where(File.task_id == task_id)
        .order_by(File.created_at.desc(), File.original_name)
    )
    return list(result.scalars().all())


async def list_all_for_project(session: AsyncSession, project_id: UUID) -> list[File]:
    result = await session.execute(
        select(File)
        .outerjoin(Task, File.task_id == Task.id)
        .where(or_(File.project_id == project_id, Task.project_id == project_id))
        .order_by(File.created_at.desc(), File.id)
    )
    return list(result.scalars().all())


async def list_all_for_team(session: AsyncSession, team_id: UUID) -> list[File]:
    result = await session.execute(
        select(File)
        .outerjoin(Task, File.task_id == Task.id)
        .join(
            Project,
            or_(File.project_id == Project.id, Task.project_id == Project.id),
        )
        .where(Project.team_id == team_id)
        .order_by(File.created_at.desc(), File.id)
    )
    return list(result.scalars().all())


async def delete_file(session: AsyncSession, file: File) -> None:
    await session.delete(file)


def update_file_metadata(file: File, *, original_name: str) -> File:
    file.original_name = original_name
    return file


async def list_accessible_file_index(
    session: AsyncSession,
    *,
    can_access_all_files: bool,
    leader_team_ids: frozenset[UUID],
    accessible_project_ids: frozenset[UUID],
    collaborative_task_ids: frozenset[UUID],
    personal_task_ids: frozenset[UUID],
    query: str | None = None,
    team_id: UUID | None = None,
    project_id: UUID | None = None,
    task_id: UUID | None = None,
) -> list[FileIndexRow]:
    statement = _file_index_statement()
    if not can_access_all_files:
        statement = statement.where(
            _file_access_condition(
                leader_team_ids,
                accessible_project_ids,
                collaborative_task_ids,
                personal_task_ids,
            )
        )
    if query:
        statement = statement.where(File.original_name.ilike(f"%{query}%"))
    if team_id is not None:
        statement = statement.where(Project.team_id == team_id)
    if project_id is not None:
        statement = statement.where(Project.id == project_id)
    if task_id is not None:
        statement = statement.where(File.task_id == task_id)
    result = await session.execute(statement.order_by(File.created_at.desc(), File.id.desc()))
    return list(result.tuples().all())


async def list_project_file_index(
    session: AsyncSession,
    project_id: UUID,
    *,
    can_access_all_files: bool,
    leader_team_ids: frozenset[UUID],
    accessible_project_ids: frozenset[UUID],
    collaborative_task_ids: frozenset[UUID],
    personal_task_ids: frozenset[UUID],
    query: str | None = None,
) -> list[FileIndexRow]:
    statement = _file_index_statement().where(Project.id == project_id)
    if not can_access_all_files:
        statement = statement.where(
            _file_access_condition(
                leader_team_ids,
                accessible_project_ids,
                collaborative_task_ids,
                personal_task_ids,
            )
        )
    if query:
        statement = statement.where(File.original_name.ilike(f"%{query}%"))
    result = await session.execute(statement.order_by(File.created_at.desc(), File.id.desc()))
    return list(result.tuples().all())


def _file_index_statement() -> Select[tuple[File, Project, Task | None, Team, User | None]]:
    statement = (
        select(File, Project, Task, Team, User)
        .outerjoin(Task, File.task_id == Task.id)
        .join(
            Project,
            or_(File.project_id == Project.id, Task.project_id == Project.id),
        )
        .join(Team, Project.team_id == Team.id)
        .outerjoin(User, File.uploaded_by_id == User.id)
    )
    return cast(Select[tuple[File, Project, Task | None, Team, User | None]], statement)


def _file_access_condition(
    leader_team_ids: frozenset[UUID],
    accessible_project_ids: frozenset[UUID],
    collaborative_task_ids: frozenset[UUID],
    personal_task_ids: frozenset[UUID],
) -> ColumnElement[bool]:
    project_access = or_(
        Project.team_id.in_(leader_team_ids),
        Project.id.in_(accessible_project_ids),
    )
    return or_(
        and_(File.project_id.is_not(None), project_access),
        and_(
            File.task_id.is_not(None),
            or_(
                Project.team_id.in_(leader_team_ids),
                and_(
                    Task.task_type == TaskType.COLLABORATIVE,
                    or_(
                        Project.id.in_(accessible_project_ids),
                        File.task_id.in_(collaborative_task_ids),
                    ),
                ),
                and_(
                    Task.task_type == TaskType.PERSONAL,
                    File.task_id.in_(personal_task_ids),
                ),
            ),
        ),
    )
