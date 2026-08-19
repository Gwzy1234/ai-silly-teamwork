from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from silly_teamwork.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from silly_teamwork.models.enums import TaskRole

if TYPE_CHECKING:
    from silly_teamwork.models.task import Task
    from silly_teamwork.models.user import User


class TaskMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "task_members"
    __table_args__ = (
        UniqueConstraint("task_id", "user_id", name="uq_task_members_task_user"),
        Index(
            "uq_task_members_one_owner",
            "task_id",
            unique=True,
            postgresql_where=text("role = 'owner'"),
            sqlite_where=text("role = 'owner'"),
        ),
    )

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[TaskRole] = mapped_column(
        Enum(TaskRole, name="task_role", values_callable=lambda enum: [e.value for e in enum]),
        default=TaskRole.OWNER,
        server_default=TaskRole.OWNER.value,
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task: Mapped[Task] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="task_members")
