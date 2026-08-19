"""Project and project-member HTTP endpoints."""

from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from silly_teamwork.api.dependencies import CurrentUser, DbSession, ProjectServiceDep
from silly_teamwork.schemas.project import (
    ProjectCreate,
    ProjectMemberAdd,
    ProjectMemberResponse,
    ProjectOwnerTransfer,
    ProjectResponse,
    ProjectStatusUpdate,
    ProjectUpdate,
)
from silly_teamwork.services.exceptions import (
    InvalidDeadlineError,
    InvalidStatusTransitionError,
    ProjectAccessDeniedError,
    ProjectMemberConflictError,
    ProjectMemberNotFoundError,
    ProjectNotFoundError,
    TeamNotFoundError,
)

router = APIRouter()
team_router = APIRouter()


def _raise_project_http_error(error: Exception) -> NoReturn:
    if isinstance(error, (ProjectNotFoundError, TeamNotFoundError)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(error, ProjectAccessDeniedError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    if isinstance(error, (ProjectMemberConflictError,)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    if isinstance(error, ProjectMemberNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(error, (InvalidDeadlineError, InvalidStatusTransitionError)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    raise error


@team_router.post(
    "/{team_id}/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
    responses={
        403: {"description": "Team leader permission required"},
        404: {"description": "Team not found"},
    },
)
async def create_project(
    team_id: UUID,
    payload: ProjectCreate,
    session: DbSession,
    current_user: CurrentUser,
    project_service: ProjectServiceDep,
) -> ProjectResponse:
    try:
        project = await project_service.create_project(session, current_user, team_id, payload)
        await session.refresh(project)
    except Exception as error:
        _raise_project_http_error(error)
    return ProjectResponse.model_validate(project)


@team_router.get(
    "/{team_id}/projects",
    response_model=list[ProjectResponse],
    summary="List accessible team projects",
    responses={404: {"description": "Team not found or not accessible"}},
)
async def list_projects(
    team_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    project_service: ProjectServiceDep,
) -> list[ProjectResponse]:
    try:
        projects = await project_service.list_projects(session, current_user, team_id)
    except Exception as error:
        _raise_project_http_error(error)
    return [ProjectResponse.model_validate(project) for project in projects]


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project details",
    responses={404: {"description": "Project not found or not accessible"}},
)
async def get_project(
    project_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    project_service: ProjectServiceDep,
) -> ProjectResponse:
    try:
        project = await project_service.get_project(session, current_user, project_id)
    except Exception as error:
        _raise_project_http_error(error)
    return ProjectResponse.model_validate(project)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update a project",
    responses={
        403: {"description": "Project management permission required"},
        404: {"description": "Project not found"},
    },
)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    session: DbSession,
    current_user: CurrentUser,
    project_service: ProjectServiceDep,
) -> ProjectResponse:
    try:
        project = await project_service.update_project(session, current_user, project_id, payload)
        await session.refresh(project)
    except Exception as error:
        _raise_project_http_error(error)
    return ProjectResponse.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a project",
    responses={
        403: {"description": "Project deletion permission required"},
        404: {"description": "Project not found"},
    },
)
async def delete_project(
    project_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    project_service: ProjectServiceDep,
) -> Response:
    try:
        await project_service.delete_project(session, current_user, project_id)
    except Exception as error:
        _raise_project_http_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/{project_id}/status",
    response_model=ProjectResponse,
    summary="Change project status",
    responses={
        400: {"description": "Invalid status transition"},
        403: {"description": "Project management permission required"},
        404: {"description": "Project not found"},
    },
)
async def change_project_status(
    project_id: UUID,
    payload: ProjectStatusUpdate,
    session: DbSession,
    current_user: CurrentUser,
    project_service: ProjectServiceDep,
) -> ProjectResponse:
    try:
        project = await project_service.update_project(
            session, current_user, project_id, ProjectUpdate(status=payload.status)
        )
        await session.refresh(project)
    except Exception as error:
        _raise_project_http_error(error)
    return ProjectResponse.model_validate(project)


@router.get(
    "/{project_id}/members",
    response_model=list[ProjectMemberResponse],
    summary="List project members",
    responses={404: {"description": "Project not found or not accessible"}},
)
async def list_project_members(
    project_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    project_service: ProjectServiceDep,
) -> list[ProjectMemberResponse]:
    try:
        members = await project_service.list_members(session, current_user, project_id)
    except Exception as error:
        _raise_project_http_error(error)
    return [ProjectMemberResponse.model_validate(member) for member in members]


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a project member",
    responses={
        403: {"description": "Project management permission required"},
        404: {"description": "Project or user not found"},
        409: {"description": "User is already a project member"},
    },
)
async def add_project_member(
    project_id: UUID,
    payload: ProjectMemberAdd,
    session: DbSession,
    current_user: CurrentUser,
    project_service: ProjectServiceDep,
) -> ProjectMemberResponse:
    try:
        member = await project_service.add_member(session, current_user, project_id, payload)
        await session.refresh(member)
    except Exception as error:
        _raise_project_http_error(error)
    return ProjectMemberResponse.model_validate(member)


@router.delete(
    "/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a project member",
    responses={
        403: {"description": "Project management permission required"},
        404: {"description": "Project member not found"},
        409: {"description": "Owner must be transferred first"},
    },
)
async def remove_project_member(
    project_id: UUID,
    user_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    project_service: ProjectServiceDep,
) -> Response:
    try:
        await project_service.remove_member(session, current_user, project_id, user_id)
    except Exception as error:
        _raise_project_http_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/{project_id}/owner",
    response_model=ProjectMemberResponse,
    summary="Transfer project ownership",
    responses={
        403: {"description": "Project management permission required"},
        404: {"description": "Project or target user not found"},
    },
)
async def transfer_project_owner(
    project_id: UUID,
    payload: ProjectOwnerTransfer,
    session: DbSession,
    current_user: CurrentUser,
    project_service: ProjectServiceDep,
) -> ProjectMemberResponse:
    try:
        owner = await project_service.transfer_owner(
            session, current_user, project_id, payload.user_id
        )
        await session.refresh(owner)
    except Exception as error:
        _raise_project_http_error(error)
    return ProjectMemberResponse.model_validate(owner)
