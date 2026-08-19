from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Enum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from silly_teamwork.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from silly_teamwork.models.enums import AIGenerationType


class AIGeneration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_generations"
    __table_args__ = (
        Index(
            "ix_ai_generations_project_user_type_created",
            "project_id",
            "user_id",
            "type",
            "created_at",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[AIGenerationType] = mapped_column(
        Enum(
            AIGenerationType,
            name="ai_generation_type",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        index=True,
        nullable=False,
    )
    request_data: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
    )
    response_data: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
    )

    # Deliberately no ORM relationships yet: persistence is an AI auxiliary
    # concern and keeping it decoupled avoids touching Project/User models.
