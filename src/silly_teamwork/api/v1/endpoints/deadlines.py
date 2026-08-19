"""Current-user deadline query HTTP endpoints."""

from typing import Annotated

from fastapi import APIRouter, Query

from silly_teamwork.api.dependencies import CurrentUser, DbSession, DeadlineServiceDep
from silly_teamwork.schemas.task import TaskResponse

router = APIRouter()


@router.get(
    "/upcoming",
    response_model=list[TaskResponse],
    summary="List tasks due within the requested time window",
)
async def list_upcoming_tasks(
    session: DbSession,
    current_user: CurrentUser,
    deadline_service: DeadlineServiceDep,
    hours: Annotated[int, Query(ge=1, le=24 * 365)] = 72,
) -> list[TaskResponse]:
    tasks = await deadline_service.get_upcoming_tasks(session, current_user, hours)
    return [TaskResponse.model_validate(task) for task in tasks]


@router.get(
    "/overdue",
    response_model=list[TaskResponse],
    summary="List overdue tasks",
)
async def list_overdue_tasks(
    session: DbSession,
    current_user: CurrentUser,
    deadline_service: DeadlineServiceDep,
) -> list[TaskResponse]:
    tasks = await deadline_service.get_overdue_tasks(session, current_user)
    return [TaskResponse.model_validate(task) for task in tasks]
