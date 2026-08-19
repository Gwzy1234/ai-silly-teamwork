"""Make user email optional.

Revision ID: 20260812_0002
Revises: 20260812_0001
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0002"
down_revision: str | None = "20260812_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(length=320),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        "UPDATE users SET email = CONCAT(id::text, '@email-unset.invalid') WHERE email IS NULL"
    )
    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(length=320),
        nullable=False,
    )
