from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.elements import ColumnElement

from silly_teamwork.models.enums import TaskStatus, TaskType
from silly_teamwork.models.project import Project
from silly_teamwork.models.task import Task
from silly_teamwork.models.task_assignment import TaskAssignment


@dataclass(frozen=True, slots=True)
class TaskAssignmentCounts:
    total: int
    todo: int
    in_progress: int
    in_review: int
    done: int
    cancelled: int

    @property
    def unfinished(self) -> int:
        return self.todo + self.in_progress + self.in_review


@dataclass(frozen=True, slots=True)
class PersonalTaskAggregate:
    task: Task
    counts: TaskAssignmentCounts


def add_all(session: AsyncSession, assignments: list[TaskAssignment]) -> None:
    session.add_all(assignments)


async def get_by_id(session: AsyncSession, assignment_id: UUID) -> TaskAssignment | None:
    result = await session.execute(
        _with_context(select(TaskAssignment).where(TaskAssignment.id == assignment_id))
    )
    return result.scalar_one_or_none()


async def get_by_id_for_update(session: AsyncSession, assignment_id: UUID) -> TaskAssignment | None:
    result = await session.execute(
        select(TaskAssignment).where(TaskAssignment.id == assignment_id).with_for_update()
    )
    return result.scalar_one_or_none()


async def get_by_task_and_user(
    session: AsyncSession, task_id: UUID, user_id: UUID
) -> TaskAssignment | None:
    result = await session.execute(
        _with_context(
            select(TaskAssignment).where(
                TaskAssignment.task_id == task_id,
                TaskAssignment.user_id == user_id,
            )
        )
    )
    return result.scalar_one_or_none()


async def list_task_ids_for_user(session: AsyncSession, user_id: UUID) -> list[UUID]:
    result = await session.execute(
        select(TaskAssignment.task_id).where(TaskAssignment.user_id == user_id)
    )
    return list(result.scalars().all())


async def list_for_task(session: AsyncSession, task_id: UUID) -> list[TaskAssignment]:
    result = await session.execute(
        _with_context(
            select(TaskAssignment)
            .where(TaskAssignment.task_id == task_id)
            .order_by(TaskAssignment.assigned_at, TaskAssignment.id)
        )
    )
    return list(result.scalars().all())


async def list_for_user(
    session: AsyncSession,
    user_id: UUID,
    *,
    status: TaskStatus | None = None,
    team_id: UUID | None = None,
    project_id: UUID | None = None,
    due_before: datetime | None = None,
    due_after: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[TaskAssignment]:
    statement = (
        select(TaskAssignment)
        .join(TaskAssignment.task)
        .join(Task.project)
        .where(
            TaskAssignment.user_id == user_id,
            Task.task_type == TaskType.PERSONAL,
        )
    )
    if status is not None:
        statement = statement.where(TaskAssignment.status == status)
    if team_id is not None:
        statement = statement.where(Project.team_id == team_id)
    if project_id is not None:
        statement = statement.where(Task.project_id == project_id)
    if due_before is not None:
        statement = statement.where(Task.due_at.is_not(None), Task.due_at <= due_before)
    if due_after is not None:
        statement = statement.where(Task.due_at.is_not(None), Task.due_at >= due_after)
    result = await session.execute(
        _with_context(
            statement.order_by(
                case(
                    (
                        TaskAssignment.status.in_(
                            (
                                TaskStatus.TODO,
                                TaskStatus.IN_PROGRESS,
                                TaskStatus.IN_REVIEW,
                            )
                        ),
                        0,
                    ),
                    else_=1,
                ),
                Task.due_at.asc().nulls_last(),
                TaskAssignment.assigned_at.desc(),
                TaskAssignment.id,
            )
            .limit(limit)
            .offset(offset)
        )
    )
    return list(result.scalars().all())


async def count_for_user(
    session: AsyncSession,
    user_id: UUID,
) -> TaskAssignmentCounts:
    statement = (
        select(
            func.count(TaskAssignment.id),
            *_status_count_expressions(),
        )
        .join(TaskAssignment.task)
        .where(
            TaskAssignment.user_id == user_id,
            Task.task_type == TaskType.PERSONAL,
        )
    )
    result = (await session.execute(statement)).one()
    return _counts_from_row(result)


async def list_personal_task_aggregates_for_project(
    session: AsyncSession,
    project_id: UUID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[PersonalTaskAggregate], int]:
    status_counts = _status_count_expressions()
    unfinished_count = status_counts[0] + status_counts[1] + status_counts[2]
    statement = (
        select(Task, func.count(TaskAssignment.id), *status_counts)
        .outerjoin(TaskAssignment, TaskAssignment.task_id == Task.id)
        .where(
            Task.project_id == project_id,
            Task.task_type == TaskType.PERSONAL,
        )
        .group_by(Task.id)
        .order_by(
            case((unfinished_count > 0, 0), else_=1),
            Task.due_at.asc().nulls_last(),
            Task.created_at.desc(),
            Task.id,
        )
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(statement)).all()
    total = await session.scalar(
        select(func.count(Task.id)).where(
            Task.project_id == project_id,
            Task.task_type == TaskType.PERSONAL,
        )
    )
    return (
        [
            PersonalTaskAggregate(
                task=row[0],
                counts=_counts_from_row(row[1:]),
            )
            for row in rows
        ],
        int(total or 0),
    )


def _status_count_expressions() -> tuple[ColumnElement[int], ...]:
    return tuple(
        func.sum(case((TaskAssignment.status == task_status, 1), else_=0))
        for task_status in (
            TaskStatus.TODO,
            TaskStatus.IN_PROGRESS,
            TaskStatus.IN_REVIEW,
            TaskStatus.DONE,
            TaskStatus.CANCELLED,
        )
    )


def _counts_from_row(row: Sequence[object]) -> TaskAssignmentCounts:
    values = tuple(int(cast(int | None, value) or 0) for value in row)
    return TaskAssignmentCounts(
        total=values[0],
        todo=values[1],
        in_progress=values[2],
        in_review=values[3],
        done=values[4],
        cancelled=values[5],
    )


def _with_context(
    statement: Select[tuple[TaskAssignment]],
) -> Select[tuple[TaskAssignment]]:
    return statement.options(
        joinedload(TaskAssignment.user),
        joinedload(TaskAssignment.task).joinedload(Task.project).joinedload(Project.team),
    )
