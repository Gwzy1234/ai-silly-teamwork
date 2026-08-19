"""Task and task-member HTTP endpoints."""

from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from silly_teamwork.api.dependencies import CurrentUser, DbSession, TaskServiceDep
from silly_teamwork.schemas.task import (
    TaskCreate,
    TaskMemberAdd,
    TaskMemberResponse,
    TaskOwnerTransfer,
    TaskResponse,
    TaskStatusUpdate,
    TaskUpdate,
)
from silly_teamwork.services.exceptions import (
    InvalidDeadlineError,
    InvalidStatusTransitionError,
    ProjectAccessDeniedError,
    ProjectMemberNotFoundError,
    ProjectNotFoundError,
    TaskAccessDeniedError,
    TaskMemberConflictError,
    TaskMemberNotFoundError,
    TaskNotFoundError,
)

router = APIRouter()
project_router = APIRouter()


def _raise_task_http_error(error: Exception) -> NoReturn:
    if isinstance(error, (ProjectNotFoundError, TaskNotFoundError)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(error, (ProjectAccessDeniedError, TaskAccessDeniedError)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    if isinstance(error, TaskMemberConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    if isinstance(error, (ProjectMemberNotFoundError, TaskMemberNotFoundError)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(error, (InvalidDeadlineError, InvalidStatusTransitionError)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    raise error


@project_router.post(
    "/{project_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task",
    responses={
        403: {"description": "Project management permission required"},
        404: {"description": "Project not found"},
    },
)
async def create_task(
    project_id: UUID,
    payload: TaskCreate,
    session: DbSession,
    current_user: CurrentUser,
    task_service: TaskServiceDep,
) -> TaskResponse:
    try:
        task = await task_service.create_task(session, current_user, project_id, payload)
        await session.refresh(task)
    except Exception as error:
        _raise_task_http_error(error)
    return TaskResponse.model_validate(task)


@project_router.get(
    "/{project_id}/tasks",
    response_model=list[TaskResponse],
    summary="List project tasks",
    responses={404: {"description": "Project not found or not accessible"}},
)
async def list_tasks(
    project_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    task_service: TaskServiceDep,
) -> list[TaskResponse]:
    try:
        tasks = await task_service.list_tasks(session, current_user, project_id)
    except Exception as error:
        _raise_task_http_error(error)
    return [TaskResponse.model_validate(task) for task in tasks]


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get task details",
    responses={404: {"description": "Task not found or not accessible"}},
)
async def get_task(
    task_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    task_service: TaskServiceDep,
) -> TaskResponse:
    try:
        task = await task_service.get_task(session, current_user, task_id)
    except Exception as error:
        _raise_task_http_error(error)
    return TaskResponse.model_validate(task)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Update a task",
    responses={
        403: {"description": "Task management permission required"},
        404: {"description": "Task not found"},
    },
)
async def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    session: DbSession,
    current_user: CurrentUser,
    task_service: TaskServiceDep,
) -> TaskResponse:
    try:
        task = await task_service.update_task(session, current_user, task_id, payload)
        await session.refresh(task)
    except Exception as error:
        _raise_task_http_error(error)
    return TaskResponse.model_validate(task)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
    responses={
        403: {"description": "Task deletion permission required"},
        404: {"description": "Task not found"},
    },
)
async def delete_task(
    task_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    task_service: TaskServiceDep,
) -> Response:
    try:
        await task_service.delete_task(session, current_user, task_id)
    except Exception as error:
        _raise_task_http_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/{task_id}/status",
    response_model=TaskResponse,
    summary="Change task status",
    responses={
        400: {"description": "Invalid status transition"},
        403: {"description": "Task status permission required"},
        404: {"description": "Task not found or not accessible"},
    },
)
async def change_task_status(
    task_id: UUID,
    payload: TaskStatusUpdate,
    session: DbSession,
    current_user: CurrentUser,
    task_service: TaskServiceDep,
) -> TaskResponse:
    try:
        task = await task_service.change_status(session, current_user, task_id, payload.status)
        await session.refresh(task)
    except Exception as error:
        _raise_task_http_error(error)
    return TaskResponse.model_validate(task)


@router.get(
    "/{task_id}/members",
    response_model=list[TaskMemberResponse],
    summary="List task members",
    responses={404: {"description": "Task not found or not accessible"}},
)
async def list_task_members(
    task_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    task_service: TaskServiceDep,
) -> list[TaskMemberResponse]:
    try:
        members = await task_service.list_members(session, current_user, task_id)
    except Exception as error:
        _raise_task_http_error(error)
    return [TaskMemberResponse.model_validate(member) for member in members]


@router.post(
    "/{task_id}/members",
    response_model=TaskMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a task member",
    responses={
        403: {"description": "Task management permission required"},
        404: {"description": "Task or project member not found"},
        409: {"description": "User is already a task member"},
    },
)
async def add_task_member(
    task_id: UUID,
    payload: TaskMemberAdd,
    session: DbSession,
    current_user: CurrentUser,
    task_service: TaskServiceDep,
) -> TaskMemberResponse:
    try:
        member = await task_service.add_member(session, current_user, task_id, payload)
        await session.refresh(member)
    except Exception as error:
        _raise_task_http_error(error)
    return TaskMemberResponse.model_validate(member)


@router.delete(
    "/{task_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a task member",
    responses={
        403: {"description": "Task management permission required"},
        404: {"description": "Task member not found"},
        409: {"description": "Owner must be transferred first"},
    },
)
async def remove_task_member(
    task_id: UUID,
    user_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    task_service: TaskServiceDep,
) -> Response:
    try:
        await task_service.remove_member(session, current_user, task_id, user_id)
    except Exception as error:
        _raise_task_http_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/{task_id}/owner",
    response_model=TaskMemberResponse,
    summary="Transfer task ownership",
    responses={
        403: {"description": "Project management permission required"},
        404: {"description": "Task or target project member not found"},
    },
)
async def transfer_task_owner(
    task_id: UUID,
    payload: TaskOwnerTransfer,
    session: DbSession,
    current_user: CurrentUser,
    task_service: TaskServiceDep,
) -> TaskMemberResponse:
    try:
        owner = await task_service.transfer_owner(session, current_user, task_id, payload.user_id)
        await session.refresh(owner)
    except Exception as error:
        _raise_task_http_error(error)
    return TaskMemberResponse.model_validate(owner)
