"""Add personal task type and per-user task assignments.

Revision ID: 20260815_0008
Revises: 20260813_0007
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0008"
down_revision: str | None = "20260813_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

task_type = postgresql.ENUM(
    "collaborative", "personal", name="task_type", create_type=False
)
attachment_mode = postgresql.ENUM(
    "shared", "individual", name="attachment_mode", create_type=False
)
task_status = postgresql.ENUM(
    "todo",
    "in_progress",
    "in_review",
    "done",
    "cancelled",
    name="task_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    task_type.create(bind, checkfirst=True)
    attachment_mode.create(bind, checkfirst=True)

    op.add_column(
        "tasks",
        sa.Column(
            "task_type",
            task_type,
            server_default="collaborative",
            nullable=False,
        ),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "attachment_mode",
            attachment_mode,
            server_default="shared",
            nullable=False,
        ),
    )

    op.create_table(
        "task_assignments",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", task_status, server_default="todo", nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
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
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_task_assignments_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_task_assignments_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_assignments")),
        sa.UniqueConstraint(
            "task_id", "user_id", name="uq_task_assignments_task_user"
        ),
    )
    op.create_index(
        op.f("ix_task_assignments_task_id"),
        "task_assignments",
        ["task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_assignments_user_id"),
        "task_assignments",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_assignments_user_status",
        "task_assignments",
        ["user_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_task_assignments_user_status", table_name="task_assignments"
    )
    op.drop_index(
        op.f("ix_task_assignments_user_id"), table_name="task_assignments"
    )
    op.drop_index(
        op.f("ix_task_assignments_task_id"), table_name="task_assignments"
    )
    op.drop_table("task_assignments")

    op.drop_column("tasks", "attachment_mode")
    op.drop_column("tasks", "task_type")

    bind = op.get_bind()
    attachment_mode.drop(bind, checkfirst=True)
    task_type.drop(bind, checkfirst=True)
