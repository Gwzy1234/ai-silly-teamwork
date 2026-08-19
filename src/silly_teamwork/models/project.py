from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from silly_teamwork.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from silly_teamwork.models.enums import ProjectStatus

if TYPE_CHECKING:
    from silly_teamwork.models.file import File
    from silly_teamwork.models.notification import Notification
    from silly_teamwork.models.project_member import ProjectMember
    from silly_teamwork.models.task import Task
    from silly_teamwork.models.team import Team
    from silly_teamwork.models.user import User


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "due_at IS NULL OR starts_at IS NULL OR due_at >= starts_at",
            name="due_at_not_before_starts_at",
        ),
        Index("ix_projects_team_status", "team_id", "status"),
        Index("ix_projects_status_due_at", "status", "due_at"),
    )

    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(
            ProjectStatus,
            name="project_status",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        default=ProjectStatus.PLANNING,
        server_default=ProjectStatus.PLANNING.value,
        index=True,
        nullable=False,
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    team: Mapped[Team] = relationship(back_populates="projects")
    creator: Mapped[User] = relationship(back_populates="projects_created")
    members: Mapped[list[ProjectMember]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    tasks: Mapped[list[Task]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    files: Mapped[list[File]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="related_project", passive_deletes=True
    )

    @property
    def created_by(self) -> User:
        """Backward-compatible alias for the clearer ``creator`` relationship."""

        return self.creator

    @created_by.setter
    def created_by(self, value: User) -> None:
        self.creator = value
