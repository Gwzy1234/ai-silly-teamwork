from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from silly_teamwork.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from silly_teamwork.models.enums import AttachmentMode, TaskPriority, TaskStatus, TaskType

if TYPE_CHECKING:
    from silly_teamwork.models.file import File
    from silly_teamwork.models.notification import Notification
    from silly_teamwork.models.notification_schedule import NotificationSchedule
    from silly_teamwork.models.project import Project
    from silly_teamwork.models.task_assignment import TaskAssignment
    from silly_teamwork.models.task_member import TaskMember
    from silly_teamwork.models.user import User


class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "due_at IS NULL OR starts_at IS NULL OR due_at >= starts_at",
            name="due_at_not_before_starts_at",
        ),
        Index("ix_tasks_project_status", "project_id", "status"),
        Index("ix_tasks_project_status_due_at", "project_id", "status", "due_at"),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status", values_callable=lambda enum: [e.value for e in enum]),
        default=TaskStatus.TODO,
        server_default=TaskStatus.TODO.value,
        index=True,
        nullable=False,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(
            TaskPriority,
            name="task_priority",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        default=TaskPriority.MEDIUM,
        server_default=TaskPriority.MEDIUM.value,
        index=True,
        nullable=False,
    )
    task_type: Mapped[TaskType] = mapped_column(
        Enum(
            TaskType,
            name="task_type",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=TaskType.COLLABORATIVE,
        server_default=TaskType.COLLABORATIVE.value,
        nullable=False,
    )
    attachment_mode: Mapped[AttachmentMode] = mapped_column(
        Enum(
            AttachmentMode,
            name="attachment_mode",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=AttachmentMode.SHARED,
        server_default=AttachmentMode.SHARED.value,
        nullable=False,
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="tasks")
    creator: Mapped[User] = relationship(back_populates="tasks_created")
    members: Mapped[list[TaskMember]] = relationship(
        back_populates="task", cascade="all, delete-orphan", passive_deletes=True
    )
    assignments: Mapped[list[TaskAssignment]] = relationship(
        back_populates="task", cascade="all, delete-orphan", passive_deletes=True
    )
    files: Mapped[list[File]] = relationship(
        back_populates="task", cascade="all, delete-orphan", passive_deletes=True
    )
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="related_task", passive_deletes=True
    )
    notification_schedules: Mapped[list[NotificationSchedule]] = relationship(
        back_populates="task", passive_deletes=True
    )

    @property
    def created_by(self) -> User:
        """Backward-compatible alias for the clearer ``creator`` relationship."""

        return self.creator

    @created_by.setter
    def created_by(self, value: User) -> None:
        self.creator = value
