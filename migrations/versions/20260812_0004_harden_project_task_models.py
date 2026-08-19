"""Harden project and task ownership and deadline constraints.

Revision ID: 20260812_0004
Revises: 20260812_0003
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0004"
down_revision: str | None = "20260812_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE project_role RENAME VALUE 'manager' TO 'owner'")
    op.execute("ALTER TYPE task_role RENAME VALUE 'assignee' TO 'owner'")
    op.execute("ALTER TYPE task_role ADD VALUE IF NOT EXISTS 'reviewer'")

    # The old roles did not enforce a single manager/assignee. Preserve the
    # earliest assignment as owner and safely demote any additional rows.
    op.execute(
        """
        WITH ranked_owners AS (
            SELECT id, row_number() OVER (
                PARTITION BY project_id ORDER BY joined_at, created_at, id
            ) AS owner_rank
            FROM project_members
            WHERE role = 'owner'
        )
        UPDATE project_members
        SET role = 'member'
        FROM ranked_owners
        WHERE project_members.id = ranked_owners.id
          AND ranked_owners.owner_rank > 1
        """
    )
    op.execute(
        """
        WITH ranked_owners AS (
            SELECT id, row_number() OVER (
                PARTITION BY task_id ORDER BY assigned_at, created_at, id
            ) AS owner_rank
            FROM task_members
            WHERE role = 'owner'
        )
        UPDATE task_members
        SET role = 'collaborator'
        FROM ranked_owners
        WHERE task_members.id = ranked_owners.id
          AND ranked_owners.owner_rank > 1
        """
    )

    op.add_column("projects", sa.Column("completed_at", sa.DateTime(timezone=True)))
    op.create_check_constraint(
        op.f("ck_projects_due_at_not_before_starts_at"),
        "projects",
        "due_at IS NULL OR starts_at IS NULL OR due_at >= starts_at",
    )
    op.create_check_constraint(
        op.f("ck_tasks_due_at_not_before_starts_at"),
        "tasks",
        "due_at IS NULL OR starts_at IS NULL OR due_at >= starts_at",
    )

    op.create_index("ix_projects_team_status", "projects", ["team_id", "status"])
    op.create_index("ix_projects_status_due_at", "projects", ["status", "due_at"])
    op.create_index("ix_tasks_project_status", "tasks", ["project_id", "status"])
    op.create_index(
        "ix_tasks_project_status_due_at", "tasks", ["project_id", "status", "due_at"]
    )

    op.create_index(
        "uq_project_members_one_owner",
        "project_members",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("role = 'owner'"),
    )
    op.create_index(
        "uq_task_members_one_owner",
        "task_members",
        ["task_id"],
        unique=True,
        postgresql_where=sa.text("role = 'owner'"),
    )


def downgrade() -> None:
    op.drop_index("uq_task_members_one_owner", table_name="task_members")
    op.drop_index("uq_project_members_one_owner", table_name="project_members")
    op.drop_index("ix_tasks_project_status_due_at", table_name="tasks")
    op.drop_index("ix_tasks_project_status", table_name="tasks")
    op.drop_index("ix_projects_status_due_at", table_name="projects")
    op.drop_index("ix_projects_team_status", table_name="projects")

    op.drop_constraint(
        op.f("ck_tasks_due_at_not_before_starts_at"), "tasks", type_="check"
    )
    op.drop_constraint(
        op.f("ck_projects_due_at_not_before_starts_at"), "projects", type_="check"
    )
    op.drop_column("projects", "completed_at")

    # PostgreSQL cannot remove an enum value directly. Recreate task_role while
    # mapping V1 reviewer rows back to collaborator for a complete downgrade.
    op.execute("ALTER TABLE task_members ALTER COLUMN role DROP DEFAULT")
    op.execute("CREATE TYPE task_role_previous AS ENUM ('assignee', 'collaborator')")
    op.execute(
        """
        ALTER TABLE task_members
        ALTER COLUMN role TYPE task_role_previous
        USING (
            CASE role::text
                WHEN 'owner' THEN 'assignee'
                WHEN 'reviewer' THEN 'collaborator'
                ELSE role::text
            END
        )::task_role_previous
        """
    )
    op.execute("DROP TYPE task_role")
    op.execute("ALTER TYPE task_role_previous RENAME TO task_role")
    op.execute("ALTER TABLE task_members ALTER COLUMN role SET DEFAULT 'assignee'")

    op.execute("ALTER TYPE project_role RENAME VALUE 'owner' TO 'manager'")
