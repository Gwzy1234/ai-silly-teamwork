from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    nickname: str | None = Field(validation_alias="display_name")
    email: EmailStr | None
    is_active: bool
    created_at: datetime


class AdminTeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    course_name: str | None
    created_by_id: UUID
    created_at: datetime


class AdminGlobalInviteResponse(BaseModel):
    invite_code: str
    role: str = "member"


class AdminActionResponse(BaseModel):
    message: str
