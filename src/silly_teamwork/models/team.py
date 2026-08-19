from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from silly_teamwork.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from silly_teamwork.models.invitation_code import InvitationCode
    from silly_teamwork.models.project import Project
    from silly_teamwork.models.team_member import TeamMember
    from silly_teamwork.models.user import User


class Team(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    course_name: Mapped[str | None] = mapped_column(String(160))
    created_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )

    created_by: Mapped[User] = relationship(back_populates="owned_teams")
    members: Mapped[list[TeamMember]] = relationship(
        back_populates="team", cascade="all, delete-orphan", passive_deletes=True
    )
    projects: Mapped[list[Project]] = relationship(
        back_populates="team", cascade="all, delete-orphan", passive_deletes=True
    )
    invitation_codes: Mapped[list[InvitationCode]] = relationship(
        back_populates="team", cascade="all, delete-orphan", passive_deletes=True
    )
