from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from silly_teamwork.core.config import get_settings
from silly_teamwork.models.user import User


class UserProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, max_length=100)
    bio: str | None = Field(default=None, max_length=1000)

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Nickname cannot be blank")
        return value

    @field_validator("bio")
    @classmethod
    def normalize_bio(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class PasswordChangeRequest(BaseModel):
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    username: str
    nickname: str | None = Field(validation_alias="display_name")
    email: EmailStr | None
    avatar_url: str | None
    bio: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_user(cls, user: User) -> UserResponse:
        avatar_url = None
        if user.avatar_url is not None:
            prefix = get_settings().api_v1_prefix.rstrip("/")
            avatar_url = f"{prefix}/users/{user.id}/avatar"
        return cls(
            id=user.id,
            username=user.username,
            nickname=user.display_name,
            email=user.email,
            avatar_url=avatar_url,
            bio=user.bio,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
