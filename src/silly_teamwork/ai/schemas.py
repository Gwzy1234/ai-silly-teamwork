from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from silly_teamwork.models.enums import TaskPriority


class RiskLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AIProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: UUID
    project_name: str
    status: str
    starts_at: datetime | None
    due_at: datetime | None
    member_count: int
    total_tasks: int
    completed_tasks: int
    open_tasks: int
    overdue_tasks: int


class AITaskInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None = None
    status: str
    priority: str
    task_type: str
    starts_at: datetime | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None
    owner_user_id: UUID | None = None
    owner_display_name: str | None = None
    assignee_user_ids: list[UUID] = Field(default_factory=list)


class AIMemberWorkload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    username: str
    display_name: str | None = None
    open_collaborative_tasks: int = 0
    open_personal_tasks: int = 0
    overdue_tasks: int = 0
    upcoming_tasks: int = 0
    total_open_tasks: int = 0


class AIFileUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_id: UUID
    name: str
    uploaded_by_id: UUID | None = None
    uploaded_by_name: str | None = None
    created_at: datetime
    project_id: UUID | None = None
    task_id: UUID | None = None
    task_title: str | None = None


class AIProjectSnapshot(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    summary: AIProjectSummary
    tasks: list[AITaskInfo]
    workloads: list[AIMemberWorkload]
    files: list[AIFileUpdate] = Field(default_factory=list)


class RiskAnalysisResponse(BaseModel):
    project_id: UUID
    risk_level: RiskLevel
    summary: str
    reasons: list[str]
    suggestions: list[str]
    generated_at: datetime


class TaskSuggestion(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    priority: TaskPriority = TaskPriority.MEDIUM
    starts_at: datetime | None = None
    due_at: datetime | None = None
    recommended_owner_user_id: UUID | None = None
    reason: str = Field(default="", max_length=2000)


class TaskSuggestionRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=2000)
    count: int = Field(default=5, ge=1, le=10)


class TaskSuggestionResponse(BaseModel):
    project_id: UUID
    suggestions: list[TaskSuggestion]


class WeeklyReportRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None


class WeeklyReportResponse(BaseModel):
    project_id: UUID
    period_start: date
    period_end: date
    completed_tasks: list[AITaskInfo]
    unfinished_tasks: list[AITaskInfo]
    overdue_tasks: list[AITaskInfo]
    file_updates: list[AIFileUpdate]
    summary: str
    highlights: list[str]
    risks: list[str]
    suggestions: list[str]
