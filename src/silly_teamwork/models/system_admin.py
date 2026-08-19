from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from silly_teamwork.db.base import Base, UUIDPrimaryKeyMixin
from silly_teamwork.models.enums import SystemAdminRole

if TYPE_CHECKING:
    from silly_teamwork.models.user import User


class SystemAdmin(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "system_admins"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    role: Mapped[SystemAdminRole] = mapped_column(
        Enum(
            SystemAdminRole,
            name="system_admin_role",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=SystemAdminRole.SUPER_ADMIN,
        server_default=SystemAdminRole.SUPER_ADMIN.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="system_admin")
