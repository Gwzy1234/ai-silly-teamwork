from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from silly_teamwork.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from silly_teamwork.models.enums import InvitationStatus, TeamRole

if TYPE_CHECKING:
    from silly_teamwork.models.team import Team
    from silly_teamwork.models.user import User


class InvitationCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invitation_codes"
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    team_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True
    )
    created_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    used_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    role: Mapped[TeamRole] = mapped_column(
        Enum(TeamRole, name="team_role", values_callable=lambda enum: [e.value for e in enum]),
        default=TeamRole.MEMBER,
        server_default=TeamRole.MEMBER.value,
        nullable=False,
    )
    status: Mapped[InvitationStatus] = mapped_column(
        Enum(
            InvitationStatus,
            name="invitation_status",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        default=InvitationStatus.ACTIVE,
        server_default=InvitationStatus.ACTIVE.value,
        index=True,
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    team: Mapped[Team | None] = relationship(back_populates="invitation_codes")
    created_by: Mapped[User] = relationship(
        foreign_keys=[created_by_id], back_populates="created_invitation_codes"
    )
    used_by: Mapped[User | None] = relationship(
        foreign_keys=[used_by_id], back_populates="used_invitation_codes"
    )
