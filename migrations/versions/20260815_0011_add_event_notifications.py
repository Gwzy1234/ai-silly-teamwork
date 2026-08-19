"""Add immediate collaboration event notification types and file references.

Revision ID: 20260815_0011
Revises: 20260815_0010
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0011"
down_revision: str | None = "20260815_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_NOTIFICATION_TYPES = (
    "task_due_soon",
    "task_overdue",
    "project_due_soon",
    "system",
)
NEW_NOTIFICATION_TYPES = (
    "project_created",
    "task_created",
    "file_uploaded",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for value in NEW_NOTIFICATION_TYPES:
            op.execute(
                sa.text(f"ALTER TYPE notification_type ADD VALUE IF NOT EXISTS '{value}'")
            )

    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_notifications_has_at_most_one_related_resource"),
            type_="check",
        )
        batch_op.add_column(sa.Column("related_file_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_notifications_related_file_id_files"),
            "files",
            ["related_file_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_check_constraint(
            op.f("ck_notifications_has_at_most_one_related_resource"),
            "(CASE WHEN related_task_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN related_project_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN related_file_id IS NOT NULL THEN 1 ELSE 0 END) <= 1",
        )
    op.create_index(
        op.f("ix_notifications_related_file_id"),
        "notifications",
        ["related_file_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_notifications_related_file_id"),
        table_name="notifications",
    )
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_notifications_has_at_most_one_related_resource"),
            type_="check",
        )
        batch_op.drop_constraint(
            op.f("fk_notifications_related_file_id_files"),
            type_="foreignkey",
        )
        batch_op.drop_column("related_file_id")
        batch_op.create_check_constraint(
            op.f("ck_notifications_has_at_most_one_related_resource"),
            "related_task_id IS NULL OR related_project_id IS NULL",
        )

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    new_values = ", ".join(f"'{value}'" for value in NEW_NOTIFICATION_TYPES)
    old_values = ", ".join(f"'{value}'" for value in OLD_NOTIFICATION_TYPES)
    op.execute(
        sa.text(
            f"UPDATE notifications SET type = 'system' "
            f"WHERE type::text IN ({new_values})"
        )
    )
    op.execute(
        sa.text(
            f"UPDATE notification_schedules SET notification_type = 'system' "
            f"WHERE notification_type::text IN ({new_values})"
        )
    )
    op.execute(
        "ALTER TABLE notifications ALTER COLUMN type TYPE text USING type::text"
    )
    op.execute(
        "ALTER TABLE notification_schedules ALTER COLUMN notification_type "
        "TYPE text USING notification_type::text"
    )
    op.execute("DROP TYPE notification_type")
    op.execute(f"CREATE TYPE notification_type AS ENUM ({old_values})")
    op.execute(
        "ALTER TABLE notifications ALTER COLUMN type TYPE notification_type "
        "USING type::notification_type"
    )
    op.execute(
        "ALTER TABLE notification_schedules ALTER COLUMN notification_type "
        "TYPE notification_type USING notification_type::notification_type"
    )
