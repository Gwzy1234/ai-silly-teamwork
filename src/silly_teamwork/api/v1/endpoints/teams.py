"""Team and team-member endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from silly_teamwork.api.dependencies import CurrentUser, DbSession, TeamServiceDep
from silly_teamwork.schemas.team import (
    InvitationCodeResponse,
    InvitationCreateRequest,
    TeamCreateRequest,
    TeamDetailResponse,
    TeamJoinRequest,
    TeamMemberResponse,
    TeamResponse,
    TeamRoleResponse,
)
from silly_teamwork.services.exceptions import (
    AlreadyTeamMemberError,
    InvalidInvitationError,
    TeamAccessDeniedError,
    TeamNotFoundError,
)
from silly_teamwork.services.teams import TeamMemberWithUser, TeamWithRole

router = APIRouter()


def _team_response(item: TeamWithRole) -> TeamResponse:
    return TeamResponse(
        id=item.team.id,
        name=item.team.name,
        description=item.team.description,
        course_name=item.team.course_name,
        role=TeamRoleResponse.from_model(item.role),
        created_at=item.team.created_at,
        updated_at=item.team.updated_at,
    )


def _member_response(item: TeamMemberWithUser) -> TeamMemberResponse:
    return TeamMemberResponse(
        user_id=item.user.id,
        username=item.user.username,
        nickname=item.user.display_name,
        role=TeamRoleResponse.from_model(item.membership.role),
        joined_at=item.membership.joined_at,
    )


@router.post(
    "",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a team",
)
async def create_team(
    payload: TeamCreateRequest,
    session: DbSession,
    current_user: CurrentUser,
    team_service: TeamServiceDep,
) -> TeamResponse:
    result = await team_service.create_team(session, current_user, payload)
    return _team_response(result)


@router.get("", response_model=list[TeamResponse], summary="List my teams")
async def list_my_teams(
    session: DbSession,
    current_user: CurrentUser,
    team_service: TeamServiceDep,
) -> list[TeamResponse]:
    results = await team_service.list_my_teams(session, current_user)
    return [_team_response(item) for item in results]


@router.post(
    "/join",
    response_model=TeamResponse,
    summary="Join a team using an invitation code",
    responses={
        400: {"description": "Invalid, expired, or already-used invitation"},
        409: {"description": "The user already belongs to this team"},
    },
)
async def join_team(
    payload: TeamJoinRequest,
    session: DbSession,
    current_user: CurrentUser,
    team_service: TeamServiceDep,
) -> TeamResponse:
    try:
        result = await team_service.join_team(session, current_user, payload.invite_code)
    except InvalidInvitationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except AlreadyTeamMemberError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _team_response(result)


@router.get(
    "/{team_id}",
    response_model=TeamDetailResponse,
    summary="Get team details and members",
    responses={404: {"description": "Team not found or not accessible"}},
)
async def get_team_detail(
    team_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    team_service: TeamServiceDep,
) -> TeamDetailResponse:
    try:
        team, members = await team_service.get_team_detail(session, current_user, team_id)
    except TeamNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    base = _team_response(team)
    return TeamDetailResponse(
        **base.model_dump(), members=[_member_response(item) for item in members]
    )


@router.delete(
    "/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a team",
    responses={
        403: {"description": "Team deletion permission required"},
        404: {"description": "Team not found"},
    },
)
async def delete_team(
    team_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    team_service: TeamServiceDep,
) -> Response:
    try:
        await team_service.delete_team(session, current_user, team_id)
    except TeamNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except TeamAccessDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{team_id}/invite",
    response_model=InvitationCodeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a single-use team invitation",
    responses={
        403: {"description": "Only the team leader may create invitations"},
        404: {"description": "Team not found or not accessible"},
    },
)
async def create_team_invitation(
    team_id: UUID,
    payload: InvitationCreateRequest,
    session: DbSession,
    current_user: CurrentUser,
    team_service: TeamServiceDep,
) -> InvitationCodeResponse:
    try:
        result = await team_service.create_invitation(session, current_user, team_id, payload)
    except TeamNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except TeamAccessDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    return InvitationCodeResponse(
        team_id=result.invitation.team_id,
        invite_code=result.plaintext_code,
        role=result.public_role,
    )


@router.get(
    "/{team_id}/members",
    response_model=list[TeamMemberResponse],
    summary="List team members",
    responses={404: {"description": "Team not found or not accessible"}},
)
async def list_team_members(
    team_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    team_service: TeamServiceDep,
) -> list[TeamMemberResponse]:
    try:
        members = await team_service.list_members(session, current_user, team_id)
    except TeamNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return [_member_response(item) for item in members]
