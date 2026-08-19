"""Registration, invitation registration, login, and token endpoints."""

from fastapi import APIRouter, HTTPException, status

from silly_teamwork.api.dependencies import AuthServiceDep, DbSession
from silly_teamwork.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from silly_teamwork.schemas.user import UserResponse
from silly_teamwork.services.exceptions import (
    InvalidCredentialsError,
    InvalidInvitationError,
    RegistrationConflictError,
)

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register with an invitation code",
    responses={
        400: {"description": "Invalid or expired invitation code"},
        409: {"description": "Username or email already exists"},
    },
)
async def register(
    payload: RegisterRequest, session: DbSession, auth_service: AuthServiceDep
) -> UserResponse:
    try:
        user = await auth_service.register(session, payload)
    except InvalidInvitationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except RegistrationConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return UserResponse.from_user(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and issue a JWT access token",
    responses={401: {"description": "Invalid username or password"}},
)
async def login(
    payload: LoginRequest, session: DbSession, auth_service: AuthServiceDep
) -> TokenResponse:
    try:
        return await auth_service.login(session, payload)
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
