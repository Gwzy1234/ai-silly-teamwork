from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from silly_teamwork.models.enums import NotificationType


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    type: NotificationType
    title: str
    content: str
    related_task_id: UUID | None
    related_project_id: UUID | None
    related_file_id: UUID | None
    is_read: bool
    created_at: datetime
    read_at: datetime | None


class MarkAllNotificationsReadResponse(BaseModel):
    updated_count: int
