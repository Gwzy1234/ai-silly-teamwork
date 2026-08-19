from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from silly_teamwork.models.enums import TaskStatus, TaskType
from silly_teamwork.models.project import Project
from silly_teamwork.models.task import Task

OPEN_TASK_STATUSES = (TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW)


def add(session: AsyncSession, task: Task) -> None:
    session.add(task)


async def delete(session: AsyncSession, task: Task) -> None:
    await session.delete(task)


async def get_by_id(session: AsyncSession, task_id: UUID) -> Task | None:
    return await session.get(Task, task_id)


async def get_by_id_with_project_team(
    session: AsyncSession, task_id: UUID
) -> Task | None:
    result = await session.execute(
        select(Task)
        .where(Task.id == task_id)
        .options(joinedload(Task.project).joinedload(Project.team))
    )
    return result.scalar_one_or_none()


async def get_by_id_for_update(session: AsyncSession, task_id: UUID) -> Task | None:
    result = await session.execute(select(Task).where(Task.id == task_id).with_for_update())
    return result.scalar_one_or_none()


async def get_status(session: AsyncSession, task_id: UUID) -> TaskStatus | None:
    result = await session.execute(select(Task.status).where(Task.id == task_id))
    return result.scalar_one_or_none()


async def list_for_project(
    session: AsyncSession,
    project_id: UUID,
    *,
    task_type: TaskType | None = None,
) -> list[Task]:
    statement = select(Task).where(Task.project_id == project_id)
    if task_type is not None:
        statement = statement.where(Task.task_type == task_type)
    result = await session.execute(
        statement.order_by(Task.created_at.desc(), Task.title)
    )
    return list(result.scalars().all())


async def list_due_between(
    session: AsyncSession, starts_at: datetime, ends_at: datetime
) -> list[Task]:
    result = await session.execute(
        select(Task)
        .where(
            Task.status.in_(OPEN_TASK_STATUSES),
            Task.due_at.is_not(None),
            Task.due_at >= starts_at,
            Task.due_at <= ends_at,
        )
        .order_by(Task.due_at, Task.id)
    )
    return list(result.scalars().all())


async def list_overdue(session: AsyncSession, before: datetime) -> list[Task]:
    result = await session.execute(
        select(Task)
        .where(
            Task.status.in_(OPEN_TASK_STATUSES),
            Task.due_at.is_not(None),
            Task.due_at < before,
        )
        .order_by(Task.due_at, Task.id)
    )
    return list(result.scalars().all())
