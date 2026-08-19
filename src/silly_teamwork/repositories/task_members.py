from uuid import UUID

from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.enums import TaskRole
from silly_teamwork.models.task import Task
from silly_teamwork.models.task_member import TaskMember
from silly_teamwork.models.user import User


def add(session: AsyncSession, membership: TaskMember) -> None:
    session.add(membership)


async def get_by_task_and_user(
    session: AsyncSession, task_id: UUID, user_id: UUID
) -> TaskMember | None:
    result = await session.execute(
        select(TaskMember).where(
            TaskMember.task_id == task_id,
            TaskMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_owner(
    session: AsyncSession, task_id: UUID, *, for_update: bool = False
) -> TaskMember | None:
    statement = select(TaskMember).where(
        TaskMember.task_id == task_id,
        TaskMember.role == TaskRole.OWNER,
    )
    if for_update:
        statement = statement.with_for_update()
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def list_for_task(session: AsyncSession, task_id: UUID) -> list[TaskMember]:
    result = await session.execute(
        select(TaskMember)
        .where(TaskMember.task_id == task_id)
        .order_by(TaskMember.assigned_at, TaskMember.id)
    )
    return list(result.scalars().all())


async def list_with_users_for_task(
    session: AsyncSession, task_id: UUID
) -> list[tuple[TaskMember, User]]:
    result = await session.execute(
        select(TaskMember, User)
        .join(User, User.id == TaskMember.user_id)
        .where(TaskMember.task_id == task_id)
        .order_by(TaskMember.assigned_at, User.username)
    )
    return list(result.tuples().all())


async def delete(session: AsyncSession, membership: TaskMember) -> None:
    await session.delete(membership)


async def delete_for_user_in_project(
    session: AsyncSession, project_id: UUID, user_id: UUID
) -> None:
    await session.execute(
        sql_delete(TaskMember).where(
            TaskMember.user_id == user_id,
            TaskMember.task_id.in_(select(Task.id).where(Task.project_id == project_id)),
        )
    )


async def list_task_ids_for_user(session: AsyncSession, user_id: UUID) -> set[UUID]:
    result = await session.execute(
        select(TaskMember.task_id).where(TaskMember.user_id == user_id)
    )
    return set(result.scalars().all())
