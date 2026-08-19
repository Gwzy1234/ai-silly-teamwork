"""Add future notification schedule records.

Revision ID: 20260815_0009
Revises: 20260815_0008
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0009"
down_revision: str | None = "20260815_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

notification_type = postgresql.ENUM(
    "task_due_soon",
    "task_overdue",
    "project_due_soon",
    "system",
    name="notification_type",
    create_type=False,
)
notification_schedule_status = postgresql.ENUM(
    "pending",
    "processing",
    "sent",
    "cancelled",
    "failed",
    name="notification_schedule_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    notification_schedule_status.create(bind, checkfirst=True)

    op.create_table(
        "notification_schedules",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("notification_type", notification_type, nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("task_assignment_id", sa.Uuid(), nullable=True),
        sa.Column("lead_time_minutes", sa.Integer(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at_snapshot", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            notification_schedule_status,
            server_default="pending",
            nullable=False,
        ),
        sa.Column("sent_notification_id", sa.Uuid(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "(task_id IS NOT NULL AND task_assignment_id IS NULL) OR "
            "(task_id IS NULL AND task_assignment_id IS NOT NULL)",
            name=op.f("ck_notification_schedules_has_exactly_one_target"),
        ),
        sa.CheckConstraint(
            "lead_time_minutes > 0",
            name=op.f("ck_notification_schedules_lead_time_minutes_positive"),
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name=op.f("ck_notification_schedules_attempt_count_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["sent_notification_id"],
            ["notifications.id"],
            name=op.f(
                "fk_notification_schedules_sent_notification_id_notifications"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["task_assignment_id"],
            ["task_assignments.id"],
            name=op.f(
                "fk_notification_schedules_task_assignment_id_task_assignments"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_notification_schedules_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notification_schedules_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_schedules")),
        sa.UniqueConstraint(
            "task_id",
            "user_id",
            "notification_type",
            "lead_time_minutes",
            name="uq_notification_schedules_task_user_type_lead",
        ),
        sa.UniqueConstraint(
            "task_assignment_id",
            "notification_type",
            "lead_time_minutes",
            name="uq_notification_schedules_assignment_type_lead",
        ),
    )
    op.create_index(
        "ix_notification_schedules_status_scheduled_for",
        "notification_schedules",
        ["status", "scheduled_for"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_schedules_task_id"),
        "notification_schedules",
        ["task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_schedules_task_assignment_id"),
        "notification_schedules",
        ["task_assignment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_schedules_user_id"),
        "notification_schedules",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_notification_schedules_user_id"),
        table_name="notification_schedules",
    )
    op.drop_index(
        op.f("ix_notification_schedules_task_assignment_id"),
        table_name="notification_schedules",
    )
    op.drop_index(
        op.f("ix_notification_schedules_task_id"),
        table_name="notification_schedules",
    )
    op.drop_index(
        "ix_notification_schedules_status_scheduled_for",
        table_name="notification_schedules",
    )
    op.drop_table("notification_schedules")

    notification_schedule_status.drop(op.get_bind(), checkfirst=True)
