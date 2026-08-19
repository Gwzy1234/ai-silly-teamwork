from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from silly_teamwork.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from silly_teamwork.models.enums import NotificationScheduleStatus, NotificationType

if TYPE_CHECKING:
    from silly_teamwork.models.task import Task
    from silly_teamwork.models.task_assignment import TaskAssignment
    from silly_teamwork.models.user import User


class NotificationSchedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_schedules"
    __table_args__ = (
        CheckConstraint(
            "(task_id IS NOT NULL AND task_assignment_id IS NULL) OR "
            "(task_id IS NULL AND task_assignment_id IS NOT NULL)",
            name="has_exactly_one_target",
        ),
        CheckConstraint(
            "lead_time_minutes > 0",
            name="lead_time_minutes_positive",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="attempt_count_non_negative",
        ),
        Index(
            "ix_notification_schedules_status_scheduled_for",
            "status",
            "scheduled_for",
        ),
        Index(
            "uq_notification_schedules_active_task_user_type_lead",
            "task_id",
            "user_id",
            "notification_type",
            "lead_time_minutes",
            unique=True,
            postgresql_where=text("status IN ('pending', 'processing')"),
            sqlite_where=text("status IN ('pending', 'processing')"),
        ),
        Index(
            "uq_notification_schedules_active_assignment_type_lead",
            "task_assignment_id",
            "notification_type",
            "lead_time_minutes",
            unique=True,
            postgresql_where=text("status IN ('pending', 'processing')"),
            sqlite_where=text("status IN ('pending', 'processing')"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(
            NotificationType,
            name="notification_type",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    task_assignment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("task_assignments.id", ondelete="CASCADE"), index=True
    )
    lead_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at_snapshot: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[NotificationScheduleStatus] = mapped_column(
        Enum(
            NotificationScheduleStatus,
            name="notification_schedule_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=NotificationScheduleStatus.PENDING,
        server_default=NotificationScheduleStatus.PENDING.value,
        nullable=False,
    )
    sent_notification_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("notifications.id", ondelete="SET NULL")
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="notification_schedules")
    task: Mapped[Task | None] = relationship(back_populates="notification_schedules")
    task_assignment: Mapped[TaskAssignment | None] = relationship(
        back_populates="notification_schedules"
    )
