"""User profile and account security endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse as AvatarResponse

from silly_teamwork.api.dependencies import CurrentUser, DbSession, UserServiceDep
from silly_teamwork.schemas.user import (
    PasswordChangeRequest,
    UserProfileUpdate,
    UserResponse,
)
from silly_teamwork.services.exceptions import (
    AvatarNotFoundError,
    AvatarTooLargeError,
    InvalidAvatarError,
    InvalidCurrentPasswordError,
    PasswordReuseError,
)

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the current authenticated user",
    responses={401: {"description": "Missing, invalid, or expired access token"}},
)
async def get_me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.from_user(current_user)


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update the current user's profile",
    responses={401: {"description": "Missing, invalid, or expired access token"}},
)
async def update_me(
    payload: UserProfileUpdate,
    session: DbSession,
    current_user: CurrentUser,
    user_service: UserServiceDep,
) -> UserResponse:
    user = await user_service.update_profile(session, current_user, payload)
    return UserResponse.from_user(user)


@router.patch(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change the current user's password",
    responses={
        400: {"description": "Current password is incorrect or password is reused"},
        401: {"description": "Missing, invalid, or expired access token"},
    },
)
async def change_password(
    payload: PasswordChangeRequest,
    session: DbSession,
    current_user: CurrentUser,
    user_service: UserServiceDep,
) -> Response:
    try:
        await user_service.change_password(session, current_user, payload)
    except (InvalidCurrentPasswordError, PasswordReuseError) as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/me/avatar",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload or replace the current user's avatar",
    responses={
        413: {"description": "Avatar exceeds MAX_AVATAR_SIZE"},
        415: {"description": "Unsupported or invalid avatar image"},
    },
)
async def upload_avatar(
    session: DbSession,
    current_user: CurrentUser,
    user_service: UserServiceDep,
    upload: Annotated[UploadFile, File(alias="file", description="JPEG, PNG, or WebP image")],
) -> UserResponse:
    try:
        user = await user_service.upload_avatar(session, current_user, upload)
    except AvatarTooLargeError as error:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(error)
        ) from error
    except InvalidAvatarError as error:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(error)
        ) from error
    finally:
        await upload.close()
    return UserResponse.from_user(user)


@router.delete(
    "/me/avatar",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete the current user's avatar",
    responses={404: {"description": "Avatar not found"}},
)
async def delete_avatar(
    session: DbSession,
    current_user: CurrentUser,
    user_service: UserServiceDep,
) -> Response:
    try:
        await user_service.delete_avatar(session, current_user)
    except AvatarNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{user_id}/avatar",
    summary="Read a user's avatar",
    response_class=AvatarResponse,
    responses={404: {"description": "Avatar not found"}},
)
async def get_avatar(
    user_id: UUID,
    session: DbSession,
    user_service: UserServiceDep,
) -> AvatarResponse:
    try:
        avatar = await user_service.get_avatar(session, user_id)
    except AvatarNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return AvatarResponse(
        path=avatar.path,
        media_type=avatar.content_type,
        headers={"Cache-Control": "no-cache"},
    )
