from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from silly_teamwork.db.base import Base, UUIDPrimaryKeyMixin
from silly_teamwork.models.enums import NotificationType

if TYPE_CHECKING:
    from silly_teamwork.models.file import File
    from silly_teamwork.models.project import Project
    from silly_teamwork.models.task import Task
    from silly_teamwork.models.user import User


class Notification(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN related_task_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN related_project_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN related_file_id IS NOT NULL THEN 1 ELSE 0 END) <= 1",
            name="has_at_most_one_related_resource",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(
            NotificationType,
            name="notification_type",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    related_task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL")
    )
    related_project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL")
    )
    related_file_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("files.id", ondelete="SET NULL"), index=True
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="notifications")
    related_task: Mapped[Task | None] = relationship(back_populates="notifications")
    related_project: Mapped[Project | None] = relationship(back_populates="notifications")
    related_file: Mapped[File | None] = relationship(back_populates="notifications")
