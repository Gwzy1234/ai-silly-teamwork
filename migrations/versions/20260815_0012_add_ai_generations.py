"""Add ai_generations table.

Revision ID: 20260815_0012
Revises: 20260815_0011
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0012"
down_revision: str | None = "20260815_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ai_generation_type = postgresql.ENUM(
    "risk_analysis",
    "task_suggestions",
    "weekly_report",
    name="ai_generation_type",
    create_type=False,
)


def upgrade() -> None:
    ai_generation_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "ai_generations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", ai_generation_type, nullable=False),
        sa.Column("request_data", postgresql.JSONB(), nullable=False),
        sa.Column("response_data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_ai_generations_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_ai_generations_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_generations")),
    )
    op.create_index(
        op.f("ix_ai_generations_project_id"),
        "ai_generations",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_generations_user_id"),
        "ai_generations",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_generations_type"),
        "ai_generations",
        ["type"],
        unique=False,
    )
    op.create_index(
        "ix_ai_generations_project_user_type_created",
        "ai_generations",
        ["project_id", "user_id", "type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_generations_project_user_type_created",
        table_name="ai_generations",
    )
    op.drop_index(op.f("ix_ai_generations_type"), table_name="ai_generations")
    op.drop_index(op.f("ix_ai_generations_user_id"), table_name="ai_generations")
    op.drop_index(op.f("ix_ai_generations_project_id"), table_name="ai_generations")
    op.drop_table("ai_generations")
    ai_generation_type.drop(op.get_bind(), checkfirst=True)
