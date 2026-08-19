from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from silly_teamwork.models.enums import TeamRole


class TeamRoleResponse(StrEnum):
    LEADER = "leader"
    ADMIN = "admin"
    MEMBER = "member"

    @classmethod
    def from_model(cls, role: TeamRole) -> "TeamRoleResponse":
        if role is TeamRole.OWNER:
            return cls.LEADER
        if role is TeamRole.ADMIN:
            return cls.ADMIN
        return cls.MEMBER


class InvitationRole(StrEnum):
    MEMBER = "member"
    LEADER = "leader"

    def to_model(self) -> TeamRole:
        return TeamRole.OWNER if self is InvitationRole.LEADER else TeamRole.MEMBER


class TeamCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120, examples=["Database Course Group"])
    description: str | None = Field(default=None, max_length=5000)
    course_name: str | None = Field(default=None, max_length=160, examples=["Database Systems"])

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Team name must not be blank")
        return stripped


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    course_name: str | None
    role: TeamRoleResponse
    created_at: datetime
    updated_at: datetime


class TeamMemberResponse(BaseModel):
    user_id: UUID
    username: str
    nickname: str | None
    role: TeamRoleResponse
    joined_at: datetime


class TeamDetailResponse(TeamResponse):
    members: list[TeamMemberResponse]


class InvitationCreateRequest(BaseModel):
    role: InvitationRole = InvitationRole.MEMBER


class InvitationCodeResponse(BaseModel):
    team_id: UUID
    invite_code: str
    role: InvitationRole


class TeamJoinRequest(BaseModel):
    invite_code: str = Field(min_length=1, max_length=256)
