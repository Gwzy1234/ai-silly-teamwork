from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from silly_teamwork.models.enums import TaskPriority, TaskRole, TaskStatus


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    priority: TaskPriority = TaskPriority.MEDIUM
    starts_at: datetime | None = None
    due_at: datetime | None = None
    owner_user_id: UUID | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "TaskCreate":
        if self.starts_at is not None and self.due_at is not None and self.due_at < self.starts_at:
            raise ValueError("due_at must not be before starts_at")
        return self


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    priority: TaskPriority | None = None
    starts_at: datetime | None = None
    due_at: datetime | None = None


class TaskMemberAdd(BaseModel):
    user_id: UUID
    role: TaskRole

    @model_validator(mode="after")
    def reject_owner_role(self) -> "TaskMemberAdd":
        if self.role is TaskRole.OWNER:
            raise ValueError("Use owner transfer to assign a task owner")
        return self


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TaskOwnerTransfer(BaseModel):
    user_id: UUID


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    starts_at: datetime | None
    due_at: datetime | None
    completed_at: datetime | None
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime


class TaskMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    user_id: UUID
    role: TaskRole
    assigned_at: datetime
    created_at: datetime
    updated_at: datetime
