from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from silly_teamwork.models.enums import ProjectRole, ProjectStatus


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    starts_at: datetime | None = None
    due_at: datetime | None = None
    owner_user_id: UUID | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "ProjectCreate":
        if self.starts_at is not None and self.due_at is not None and self.due_at < self.starts_at:
            raise ValueError("due_at must not be before starts_at")
        return self


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    status: ProjectStatus | None = None
    starts_at: datetime | None = None
    due_at: datetime | None = None


class ProjectMemberAdd(BaseModel):
    user_id: UUID


class ProjectStatusUpdate(BaseModel):
    status: ProjectStatus


class ProjectOwnerTransfer(BaseModel):
    user_id: UUID


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    team_id: UUID
    name: str
    description: str | None
    status: ProjectStatus
    starts_at: datetime | None
    due_at: datetime | None
    completed_at: datetime | None
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime


class ProjectMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    user_id: UUID
    role: ProjectRole
    joined_at: datetime
    created_at: datetime
    updated_at: datetime
