"""Add independent system administrator authorization.

Revision ID: 20260812_0003
Revises: 20260812_0002
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260812_0003"
down_revision: str | None = "20260812_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

system_admin_role = postgresql.ENUM("super_admin", name="system_admin_role", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    system_admin_role.create(bind, checkfirst=True)
    op.create_table(
        "system_admins",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", system_admin_role, server_default="super_admin", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_system_admins_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_system_admins")),
    )
    op.create_index(op.f("ix_system_admins_user_id"), "system_admins", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_table("system_admins")
    system_admin_role.drop(op.get_bind(), checkfirst=True)
