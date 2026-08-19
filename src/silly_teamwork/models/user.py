from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from silly_teamwork.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from silly_teamwork.models.file import File
    from silly_teamwork.models.invitation_code import InvitationCode
    from silly_teamwork.models.notification import Notification
    from silly_teamwork.models.notification_schedule import NotificationSchedule
    from silly_teamwork.models.project import Project
    from silly_teamwork.models.project_member import ProjectMember
    from silly_teamwork.models.system_admin import SystemAdmin
    from silly_teamwork.models.task import Task
    from silly_teamwork.models.task_assignment import TaskAssignment
    from silly_teamwork.models.task_member import TaskMember
    from silly_teamwork.models.team import Team
    from silly_teamwork.models.team_member import TeamMember


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    bio: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    team_memberships: Mapped[list[TeamMember]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    teams: Mapped[list[Team]] = relationship(
        secondary="team_members",
        viewonly=True,
    )
    owned_teams: Mapped[list[Team]] = relationship(
        back_populates="created_by", passive_deletes=True
    )
    project_members: Mapped[list[ProjectMember]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    projects_created: Mapped[list[Project]] = relationship(
        back_populates="creator", passive_deletes=True
    )
    task_members: Mapped[list[TaskMember]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    task_assignments: Mapped[list[TaskAssignment]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    tasks_created: Mapped[list[Task]] = relationship(
        back_populates="creator", passive_deletes=True
    )
    uploaded_files: Mapped[list[File]] = relationship(back_populates="uploaded_by")
    created_invitation_codes: Mapped[list[InvitationCode]] = relationship(
        foreign_keys="InvitationCode.created_by_id",
        back_populates="created_by",
        passive_deletes=True,
    )
    used_invitation_codes: Mapped[list[InvitationCode]] = relationship(
        foreign_keys="InvitationCode.used_by_id", back_populates="used_by"
    )
    system_admin: Mapped[SystemAdmin | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    notification_schedules: Mapped[list[NotificationSchedule]] = relationship(
        back_populates="user", passive_deletes=True
    )

    @property
    def project_memberships(self) -> list[ProjectMember]:
        """Backward-compatible alias for ``project_members``."""

        return self.project_members

    @property
    def created_projects(self) -> list[Project]:
        """Backward-compatible alias for ``projects_created``."""

        return self.projects_created

    @property
    def task_memberships(self) -> list[TaskMember]:
        """Backward-compatible alias for ``task_members``."""

        return self.task_members

    @property
    def created_tasks(self) -> list[Task]:
        """Backward-compatible alias for ``tasks_created``."""

        return self.tasks_created
