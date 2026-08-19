"""Allow historical schedules alongside one active reminder node.

Revision ID: 20260815_0010
Revises: 20260815_0009
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0010"
down_revision: str | None = "20260815_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_STATUS_PREDICATE = "status IN ('pending', 'processing')"


def upgrade() -> None:
    with op.batch_alter_table("notification_schedules") as batch_op:
        batch_op.drop_constraint(
            "uq_notification_schedules_task_user_type_lead",
            type_="unique",
        )
        batch_op.drop_constraint(
            "uq_notification_schedules_assignment_type_lead",
            type_="unique",
        )
    op.create_index(
        "uq_notification_schedules_active_task_user_type_lead",
        "notification_schedules",
        ["task_id", "user_id", "notification_type", "lead_time_minutes"],
        unique=True,
        postgresql_where=sa.text(ACTIVE_STATUS_PREDICATE),
    )
    op.create_index(
        "uq_notification_schedules_active_assignment_type_lead",
        "notification_schedules",
        ["task_assignment_id", "notification_type", "lead_time_minutes"],
        unique=True,
        postgresql_where=sa.text(ACTIVE_STATUS_PREDICATE),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_notification_schedules_active_assignment_type_lead",
        table_name="notification_schedules",
    )
    op.drop_index(
        "uq_notification_schedules_active_task_user_type_lead",
        table_name="notification_schedules",
    )
    with op.batch_alter_table("notification_schedules") as batch_op:
        batch_op.create_unique_constraint(
            "uq_notification_schedules_assignment_type_lead",
            ["task_assignment_id", "notification_type", "lead_time_minutes"],
        )
        batch_op.create_unique_constraint(
            "uq_notification_schedules_task_user_type_lead",
            ["task_id", "user_id", "notification_type", "lead_time_minutes"],
        )
