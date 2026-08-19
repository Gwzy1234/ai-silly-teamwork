"""System-wide administration endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from silly_teamwork.api.dependencies import AdminServiceDep, CurrentSystemAdmin, DbSession
from silly_teamwork.schemas.admin import (
    AdminActionResponse,
    AdminGlobalInviteResponse,
    AdminTeamResponse,
    AdminUserResponse,
)
from silly_teamwork.services.exceptions import AdminTargetNotFoundError

router = APIRouter()


@router.get("/users", response_model=list[AdminUserResponse], summary="List all users")
async def list_users(
    session: DbSession,
    _: CurrentSystemAdmin,
    admin_service: AdminServiceDep,
) -> list[AdminUserResponse]:
    users = await admin_service.list_users(session)
    return [AdminUserResponse.model_validate(user) for user in users]


@router.post(
    "/users/{user_id}/ban",
    response_model=AdminActionResponse,
    summary="Ban a user without deleting historical data",
    responses={404: {"description": "User not found"}},
)
async def ban_user(
    user_id: UUID,
    session: DbSession,
    _: CurrentSystemAdmin,
    admin_service: AdminServiceDep,
) -> AdminActionResponse:
    try:
        await admin_service.set_user_active(session, user_id, is_active=False)
    except AdminTargetNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return AdminActionResponse(message="User banned")


@router.post(
    "/users/{user_id}/unban",
    response_model=AdminActionResponse,
    summary="Unban a user",
    responses={404: {"description": "User not found"}},
)
async def unban_user(
    user_id: UUID,
    session: DbSession,
    _: CurrentSystemAdmin,
    admin_service: AdminServiceDep,
) -> AdminActionResponse:
    try:
        await admin_service.set_user_active(session, user_id, is_active=True)
    except AdminTargetNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return AdminActionResponse(message="User unbanned")


@router.delete(
    "/teams/{team_id}/members/{user_id}",
    response_model=AdminActionResponse,
    summary="Remove a user from a team",
    responses={404: {"description": "Team or membership not found"}},
)
async def remove_team_member(
    team_id: UUID,
    user_id: UUID,
    session: DbSession,
    _: CurrentSystemAdmin,
    admin_service: AdminServiceDep,
) -> AdminActionResponse:
    try:
        await admin_service.remove_team_member(session, team_id, user_id)
    except AdminTargetNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return AdminActionResponse(message="User removed from team")


@router.post(
    "/invites",
    response_model=AdminGlobalInviteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a single-use global registration invitation",
)
async def create_global_invitation(
    session: DbSession,
    current_admin: CurrentSystemAdmin,
    admin_service: AdminServiceDep,
) -> AdminGlobalInviteResponse:
    result = await admin_service.create_global_invitation(session, current_admin)
    return AdminGlobalInviteResponse(invite_code=result.plaintext_code)


@router.get("/teams", response_model=list[AdminTeamResponse], summary="List all teams")
async def list_teams(
    session: DbSession,
    _: CurrentSystemAdmin,
    admin_service: AdminServiceDep,
) -> list[AdminTeamResponse]:
    teams = await admin_service.list_teams(session)
    return [AdminTeamResponse.model_validate(team) for team in teams]
