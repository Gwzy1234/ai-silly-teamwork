from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from silly_teamwork.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from silly_teamwork.models.enums import TaskStatus

if TYPE_CHECKING:
    from silly_teamwork.models.notification_schedule import NotificationSchedule
    from silly_teamwork.models.task import Task
    from silly_teamwork.models.user import User


class TaskAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "task_assignments"
    __table_args__ = (
        UniqueConstraint(
            "task_id", "user_id", name="uq_task_assignments_task_user"
        ),
        Index("ix_task_assignments_user_status", "user_id", "status"),
    )

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[TaskStatus] = mapped_column(
        Enum(
            TaskStatus,
            name="task_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=TaskStatus.TODO,
        server_default=TaskStatus.TODO.value,
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    task: Mapped[Task] = relationship(back_populates="assignments")
    user: Mapped[User] = relationship(back_populates="task_assignments")
    notification_schedules: Mapped[list[NotificationSchedule]] = relationship(
        back_populates="task_assignment", passive_deletes=True
    )
