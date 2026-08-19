from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from silly_teamwork.models.enums import (
    AttachmentMode,
    TaskPriority,
    TaskStatus,
    TaskType,
)
from silly_teamwork.models.task import Task
from silly_teamwork.models.task_assignment import TaskAssignment

if TYPE_CHECKING:
    from silly_teamwork.repositories.task_assignments import (
        PersonalTaskAggregate,
        TaskAssignmentCounts,
    )


class PersonalTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    priority: TaskPriority = TaskPriority.MEDIUM
    starts_at: datetime | None = None
    due_at: datetime | None = None
    assignee_user_ids: list[UUID]
    attachment_mode: AttachmentMode = AttachmentMode.SHARED

    @field_validator("title")
    @classmethod
    def reject_blank_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Task title must not be blank")
        return stripped

    @model_validator(mode="after")
    def validate_dates(self) -> "PersonalTaskCreate":
        if self.starts_at is not None and self.due_at is not None and self.due_at < self.starts_at:
            raise ValueError("due_at must not be before starts_at")
        return self


class PersonalTaskTeamSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class PersonalTaskProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    team: PersonalTaskTeamSummary


class PersonalTaskSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    project: PersonalTaskProjectSummary
    title: str
    description: str | None
    priority: TaskPriority
    task_type: TaskType
    attachment_mode: AttachmentMode
    starts_at: datetime | None
    due_at: datetime | None
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime


class TaskAssignmentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    nickname: str | None

    @classmethod
    def from_assignment(cls, assignment: TaskAssignment) -> "TaskAssignmentUserResponse":
        return cls(
            id=assignment.user.id,
            username=assignment.user.username,
            nickname=assignment.user.display_name,
        )


class TaskAssignmentResponse(BaseModel):
    id: UUID
    task_id: UUID
    user_id: UUID
    user: TaskAssignmentUserResponse
    status: TaskStatus
    assigned_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_assignment(cls, assignment: TaskAssignment) -> "TaskAssignmentResponse":
        return cls(
            id=assignment.id,
            task_id=assignment.task_id,
            user_id=assignment.user_id,
            user=TaskAssignmentUserResponse.from_assignment(assignment),
            status=assignment.status,
            assigned_at=assignment.assigned_at,
            started_at=assignment.started_at,
            completed_at=assignment.completed_at,
            created_at=assignment.created_at,
            updated_at=assignment.updated_at,
        )


class PersonalTaskCreateResponse(BaseModel):
    task: PersonalTaskSummaryResponse
    assignments: list[TaskAssignmentResponse]

    @classmethod
    def from_records(
        cls, task: Task, assignments: list[TaskAssignment]
    ) -> "PersonalTaskCreateResponse":
        return cls(
            task=PersonalTaskSummaryResponse.model_validate(task),
            assignments=[
                TaskAssignmentResponse.from_orm_assignment(assignment) for assignment in assignments
            ],
        )


class PersonalTaskDetailResponse(BaseModel):
    task: PersonalTaskSummaryResponse
    my_assignment: TaskAssignmentResponse | None

    @classmethod
    def from_records(
        cls, task: Task, assignment: TaskAssignment | None
    ) -> "PersonalTaskDetailResponse":
        return cls(
            task=PersonalTaskSummaryResponse.model_validate(task),
            my_assignment=(
                None
                if assignment is None
                else TaskAssignmentResponse.from_orm_assignment(assignment)
            ),
        )


class MyPersonalTaskResponse(BaseModel):
    assignment: TaskAssignmentResponse
    task: PersonalTaskSummaryResponse

    @classmethod
    def from_assignment(cls, assignment: TaskAssignment) -> "MyPersonalTaskResponse":
        return cls(
            assignment=TaskAssignmentResponse.from_orm_assignment(assignment),
            task=PersonalTaskSummaryResponse.model_validate(assignment.task),
        )


class MyPersonalTaskCountResponse(BaseModel):
    total: int = Field(ge=0)
    unfinished: int = Field(ge=0)
    todo: int = Field(ge=0)
    in_progress: int = Field(ge=0)
    in_review: int = Field(ge=0)
    done: int = Field(ge=0)
    cancelled: int = Field(ge=0)

    @classmethod
    def from_counts(cls, counts: "TaskAssignmentCounts") -> "MyPersonalTaskCountResponse":
        return cls(
            total=counts.total,
            unfinished=counts.unfinished,
            todo=counts.todo,
            in_progress=counts.in_progress,
            in_review=counts.in_review,
            done=counts.done,
            cancelled=counts.cancelled,
        )


class ProjectPersonalTaskListItemResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    priority: TaskPriority
    attachment_mode: AttachmentMode
    starts_at: datetime | None
    due_at: datetime | None
    created_at: datetime
    assignment_total: int = Field(ge=0)
    todo_count: int = Field(ge=0)
    in_progress_count: int = Field(ge=0)
    in_review_count: int = Field(ge=0)
    done_count: int = Field(ge=0)
    cancelled_count: int = Field(ge=0)

    @classmethod
    def from_aggregate(
        cls, aggregate: "PersonalTaskAggregate"
    ) -> "ProjectPersonalTaskListItemResponse":
        task = aggregate.task
        counts = aggregate.counts
        return cls(
            id=task.id,
            title=task.title,
            description=task.description,
            priority=task.priority,
            attachment_mode=task.attachment_mode,
            starts_at=task.starts_at,
            due_at=task.due_at,
            created_at=task.created_at,
            assignment_total=counts.total,
            todo_count=counts.todo,
            in_progress_count=counts.in_progress,
            in_review_count=counts.in_review,
            done_count=counts.done,
            cancelled_count=counts.cancelled,
        )


class ProjectPersonalTaskPageResponse(BaseModel):
    items: list[ProjectPersonalTaskListItemResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)

    @classmethod
    def from_records(
        cls,
        records: list["PersonalTaskAggregate"],
        *,
        total: int,
        limit: int,
        offset: int,
    ) -> "ProjectPersonalTaskPageResponse":
        return cls(
            items=[
                ProjectPersonalTaskListItemResponse.from_aggregate(record) for record in records
            ],
            total=total,
            limit=limit,
            offset=offset,
        )
