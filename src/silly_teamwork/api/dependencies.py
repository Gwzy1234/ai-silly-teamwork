from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.ai.service import AIAssistantService, get_ai_assistant_service
from silly_teamwork.core.security import decode_access_token
from silly_teamwork.db.session import get_db_session
from silly_teamwork.models.user import User
from silly_teamwork.repositories import system_admins, users
from silly_teamwork.services.admin import AdminService, get_admin_service
from silly_teamwork.services.auth import AuthService, get_auth_service
from silly_teamwork.services.deadlines import DeadlineService, get_deadline_service
from silly_teamwork.services.files import FileService, get_file_service
from silly_teamwork.services.notifications import NotificationService, get_notification_service
from silly_teamwork.services.personal_tasks import PersonalTaskService, get_personal_task_service
from silly_teamwork.services.projects import ProjectService, get_project_service
from silly_teamwork.services.task_assignments import (
    TaskAssignmentService,
    get_task_assignment_service,
)
from silly_teamwork.services.tasks import TaskService, get_task_service
from silly_teamwork.services.teams import TeamService, get_team_service
from silly_teamwork.services.users import UserService, get_user_service

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
TeamServiceDep = Annotated[TeamService, Depends(get_team_service)]
AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
FileServiceDep = Annotated[FileService, Depends(get_file_service)]
NotificationServiceDep = Annotated[NotificationService, Depends(get_notification_service)]
DeadlineServiceDep = Annotated[DeadlineService, Depends(get_deadline_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
PersonalTaskServiceDep = Annotated[
    PersonalTaskService, Depends(get_personal_task_service)
]
TaskAssignmentServiceDep = Annotated[
    TaskAssignmentService, Depends(get_task_assignment_service)
]
AIAssistantServiceDep = Annotated[
    AIAssistantService, Depends(get_ai_assistant_service)
]

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="JWT access token returned by POST /api/v1/auth/login",
)


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _credentials_error()

    try:
        payload = decode_access_token(credentials.credentials)
        subject = payload.get("sub")
        user_id = UUID(subject) if isinstance(subject, str) else None
    except (jwt.InvalidTokenError, ValueError, TypeError) as error:
        raise _credentials_error() from error

    if user_id is None:
        raise _credentials_error()

    user = await users.get_by_id(session, user_id)
    if user is None or not user.is_active:
        raise _credentials_error()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_system_admin(session: DbSession, current_user: CurrentUser) -> User:
    authorization = await system_admins.get_by_user_id(session, current_user.id)
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System administrator access required",
        )
    return current_user


CurrentSystemAdmin = Annotated[User, Depends(get_current_system_admin)]
