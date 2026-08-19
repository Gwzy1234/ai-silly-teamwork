"""Personal-task and task-assignment HTTP endpoints."""

from datetime import datetime
from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from silly_teamwork.api.dependencies import (
    CurrentUser,
    DbSession,
    PersonalTaskServiceDep,
    TaskAssignmentServiceDep,
)
from silly_teamwork.models.enums import TaskStatus
from silly_teamwork.schemas.personal_task import (
    MyPersonalTaskCountResponse,
    MyPersonalTaskResponse,
    PersonalTaskCreate,
    PersonalTaskCreateResponse,
    PersonalTaskDetailResponse,
    ProjectPersonalTaskPageResponse,
    TaskAssignmentResponse,
)
from silly_teamwork.schemas.task import TaskStatusUpdate
from silly_teamwork.services.exceptions import (
    InvalidDeadlineError,
    InvalidStatusTransitionError,
    PersonalTaskValidationError,
    ProjectAccessDeniedError,
    ProjectNotFoundError,
    TaskAccessDeniedError,
    TaskAssignmentAccessDeniedError,
    TaskAssignmentNotFoundError,
    TaskNotFoundError,
)

project_router = APIRouter()
my_tasks_router = APIRouter()
personal_task_router = APIRouter()
assignment_router = APIRouter()


def _raise_personal_task_http_error(error: Exception) -> NoReturn:
    if isinstance(
        error,
        (ProjectNotFoundError, TaskNotFoundError, TaskAssignmentNotFoundError),
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(
        error,
        (
            ProjectAccessDeniedError,
            TaskAccessDeniedError,
            TaskAssignmentAccessDeniedError,
        ),
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    if isinstance(
        error,
        (
            InvalidDeadlineError,
            InvalidStatusTransitionError,
            PersonalTaskValidationError,
        ),
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    raise error


@project_router.post(
    "/{project_id}/personal-tasks",
    response_model=PersonalTaskCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a personal task",
    responses={
        400: {"description": "Invalid personal-task input"},
        403: {"description": "Team leader or system administrator required"},
        404: {"description": "Project not found"},
    },
)
async def create_personal_task(
    project_id: UUID,
    payload: PersonalTaskCreate,
    session: DbSession,
    current_user: CurrentUser,
    personal_task_service: PersonalTaskServiceDep,
) -> PersonalTaskCreateResponse:
    try:
        created = await personal_task_service.create_personal_task(
            session, current_user, project_id, payload
        )
        task = await personal_task_service.get_personal_task(session, current_user, created.id)
        assignments = await personal_task_service.list_assignments(
            session, current_user, created.id
        )
    except Exception as error:
        _raise_personal_task_http_error(error)
    return PersonalTaskCreateResponse.from_records(task, assignments)


@project_router.get(
    "/{project_id}/personal-tasks",
    response_model=ProjectPersonalTaskPageResponse,
    summary="List project personal tasks",
    responses={
        403: {"description": "Team leader or system administrator required"},
        404: {"description": "Project not found"},
    },
)
async def list_project_personal_tasks(
    project_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    personal_task_service: PersonalTaskServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProjectPersonalTaskPageResponse:
    try:
        records, total = await personal_task_service.list_project_personal_tasks(
            session,
            current_user,
            project_id,
            limit=limit,
            offset=offset,
        )
    except Exception as error:
        _raise_personal_task_http_error(error)
    return ProjectPersonalTaskPageResponse.from_records(
        records,
        total=total,
        limit=limit,
        offset=offset,
    )


@my_tasks_router.get(
    "/my",
    response_model=list[MyPersonalTaskResponse],
    summary="List my personal-task assignments",
)
async def list_my_personal_tasks(
    session: DbSession,
    current_user: CurrentUser,
    assignment_service: TaskAssignmentServiceDep,
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
    team_id: UUID | None = None,
    project_id: UUID | None = None,
    due_before: datetime | None = None,
    due_after: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[MyPersonalTaskResponse]:
    assignments = await assignment_service.list_my_assignments(
        session,
        current_user,
        status=status_filter,
        team_id=team_id,
        project_id=project_id,
        due_before=due_before,
        due_after=due_after,
        limit=limit,
        offset=offset,
    )
    return [MyPersonalTaskResponse.from_assignment(assignment) for assignment in assignments]


@my_tasks_router.get(
    "/my/count",
    response_model=MyPersonalTaskCountResponse,
    summary="Count my personal-task assignments",
)
async def count_my_personal_tasks(
    session: DbSession,
    current_user: CurrentUser,
    assignment_service: TaskAssignmentServiceDep,
) -> MyPersonalTaskCountResponse:
    counts = await assignment_service.count_my_assignments(session, current_user)
    return MyPersonalTaskCountResponse.from_counts(counts)


@personal_task_router.get(
    "/{task_id}",
    response_model=PersonalTaskDetailResponse,
    summary="Get personal-task details",
    responses={404: {"description": "Personal task not found or not accessible"}},
)
async def get_personal_task(
    task_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    personal_task_service: PersonalTaskServiceDep,
    assignment_service: TaskAssignmentServiceDep,
) -> PersonalTaskDetailResponse:
    try:
        task = await personal_task_service.get_personal_task(session, current_user, task_id)
        own_assignment = await assignment_service.get_my_assignment_for_task(
            session, current_user, task_id
        )
    except Exception as error:
        _raise_personal_task_http_error(error)
    return PersonalTaskDetailResponse.from_records(task, own_assignment)


@personal_task_router.get(
    "/{task_id}/assignments",
    response_model=list[TaskAssignmentResponse],
    summary="List personal-task progress",
    responses={
        403: {"description": "Team leader or system administrator required"},
        404: {"description": "Personal task not found"},
    },
)
async def list_personal_task_assignments(
    task_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    personal_task_service: PersonalTaskServiceDep,
) -> list[TaskAssignmentResponse]:
    try:
        assignments = await personal_task_service.list_assignments(session, current_user, task_id)
    except Exception as error:
        _raise_personal_task_http_error(error)
    return [TaskAssignmentResponse.from_orm_assignment(assignment) for assignment in assignments]


@personal_task_router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a personal task",
    responses={
        403: {"description": "Team leader or system administrator required"},
        404: {"description": "Personal task not found"},
    },
)
async def delete_personal_task(
    task_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    personal_task_service: PersonalTaskServiceDep,
) -> Response:
    try:
        await personal_task_service.delete_personal_task(session, current_user, task_id)
    except Exception as error:
        _raise_personal_task_http_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@assignment_router.get(
    "/{assignment_id}",
    response_model=TaskAssignmentResponse,
    summary="Get a task assignment",
    responses={404: {"description": "Task assignment not found or not accessible"}},
)
async def get_task_assignment(
    assignment_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    assignment_service: TaskAssignmentServiceDep,
) -> TaskAssignmentResponse:
    try:
        assignment = await assignment_service.get_assignment(session, current_user, assignment_id)
    except Exception as error:
        _raise_personal_task_http_error(error)
    return TaskAssignmentResponse.from_orm_assignment(assignment)


@assignment_router.patch(
    "/{assignment_id}/status",
    response_model=TaskAssignmentResponse,
    summary="Change my task-assignment status",
    responses={
        400: {"description": "Invalid status transition"},
        403: {"description": "Only the assigned user can change this status"},
        404: {"description": "Task assignment not found"},
    },
)
async def change_task_assignment_status(
    assignment_id: UUID,
    payload: TaskStatusUpdate,
    session: DbSession,
    current_user: CurrentUser,
    assignment_service: TaskAssignmentServiceDep,
) -> TaskAssignmentResponse:
    try:
        assignment = await assignment_service.change_status(
            session, current_user, assignment_id, payload.status
        )
    except Exception as error:
        _raise_personal_task_http_error(error)
    return TaskAssignmentResponse.from_orm_assignment(assignment)
