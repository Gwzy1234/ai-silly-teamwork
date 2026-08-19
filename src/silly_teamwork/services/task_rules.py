from datetime import datetime

from silly_teamwork.models.enums import TaskStatus
from silly_teamwork.services.exceptions import InvalidDeadlineError

TASK_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.TODO: frozenset({TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED}),
    TaskStatus.IN_PROGRESS: frozenset(
        {TaskStatus.TODO, TaskStatus.IN_REVIEW, TaskStatus.DONE, TaskStatus.CANCELLED}
    ),
    TaskStatus.IN_REVIEW: frozenset(
        {TaskStatus.IN_PROGRESS, TaskStatus.DONE, TaskStatus.CANCELLED}
    ),
    TaskStatus.DONE: frozenset({TaskStatus.IN_PROGRESS}),
    TaskStatus.CANCELLED: frozenset({TaskStatus.TODO}),
}


def validate_task_dates(starts_at: datetime | None, due_at: datetime | None) -> None:
    if starts_at is not None and due_at is not None and due_at < starts_at:
        raise InvalidDeadlineError("due_at must not be before starts_at")
