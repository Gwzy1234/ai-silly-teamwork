"""Current-user notification HTTP endpoints."""

from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from silly_teamwork.api.dependencies import (
    CurrentUser,
    DbSession,
    NotificationServiceDep,
)
from silly_teamwork.schemas.notification import (
    MarkAllNotificationsReadResponse,
    NotificationResponse,
)
from silly_teamwork.services.exceptions import NotificationNotFoundError

router = APIRouter()


def _raise_notification_http_error(error: Exception) -> NoReturn:
    if isinstance(error, NotificationNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    raise error


@router.get(
    "",
    response_model=list[NotificationResponse],
    summary="List current user notifications",
)
async def list_notifications(
    session: DbSession,
    current_user: CurrentUser,
    notification_service: NotificationServiceDep,
) -> list[NotificationResponse]:
    notifications = await notification_service.list_user_notifications(session, current_user)
    return [NotificationResponse.model_validate(item) for item in notifications]


@router.patch(
    "/read-all",
    response_model=MarkAllNotificationsReadResponse,
    summary="Mark all current user notifications as read",
)
async def mark_all_notifications_as_read(
    session: DbSession,
    current_user: CurrentUser,
    notification_service: NotificationServiceDep,
) -> MarkAllNotificationsReadResponse:
    count = await notification_service.mark_all_as_read(session, current_user)
    return MarkAllNotificationsReadResponse(updated_count=count)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark a notification as read",
    responses={404: {"description": "Notification not found"}},
)
async def mark_notification_as_read(
    notification_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    notification_service: NotificationServiceDep,
) -> NotificationResponse:
    try:
        notification = await notification_service.mark_as_read(
            session, current_user, notification_id
        )
    except Exception as error:
        _raise_notification_http_error(error)
    return NotificationResponse.model_validate(notification)
