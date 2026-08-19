"""Add indexes for permission-aware file index queries.

Revision ID: 20260813_0007
Revises: 20260813_0006
Create Date: 2026-08-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260813_0007"
down_revision: str | None = "20260813_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_files_project_created_id",
        "files",
        ["project_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_files_task_created_id",
        "files",
        ["task_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_files_uploader_created_id",
        "files",
        ["uploaded_by_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_files_created_id",
        "files",
        ["created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_files_created_id", table_name="files")
    op.drop_index("ix_files_uploader_created_id", table_name="files")
    op.drop_index("ix_files_task_created_id", table_name="files")
    op.drop_index("ix_files_project_created_id", table_name="files")
