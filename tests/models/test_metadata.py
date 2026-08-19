from sqlalchemy.orm import configure_mappers

import silly_teamwork.models  # noqa: F401
from silly_teamwork.db.base import Base


def test_all_expected_tables_are_registered() -> None:
    configure_mappers()

    assert set(Base.metadata.tables) == {
        "files",
        "invitation_codes",
        "notifications",
        "notification_schedules",
        "project_members",
        "projects",
        "system_admins",
        "task_members",
        "task_assignments",
        "tasks",
        "team_members",
        "teams",
        "users",
    }


def test_membership_tables_prevent_duplicate_members() -> None:
    expected_unique_columns = {
        "team_members": {"team_id", "user_id"},
        "project_members": {"project_id", "user_id"},
        "task_members": {"task_id", "user_id"},
        "task_assignments": {"task_id", "user_id"},
    }

    for table_name, expected_columns in expected_unique_columns.items():
        table = Base.metadata.tables[table_name]
        unique_column_sets = {
            frozenset(column.name for column in constraint.columns)
            for constraint in table.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }
        assert frozenset(expected_columns) in unique_column_sets


def test_every_business_table_has_standard_audit_columns() -> None:
    for table_name, table in Base.metadata.tables.items():
        if table_name == "system_admins":
            assert {"id", "user_id", "role", "created_at"} == set(table.columns.keys())
            continue
        if table_name == "notifications":
            assert {"id", "created_at", "read_at"}.issubset(table.columns.keys())
            continue
        assert {"id", "created_at", "updated_at"}.issubset(table.columns.keys())


def test_user_email_is_optional() -> None:
    assert Base.metadata.tables["users"].c.email.nullable is True


def test_notification_indexes_and_history_preserving_foreign_keys() -> None:
    table = Base.metadata.tables["notifications"]
    indexed_columns = {
        tuple(column.name for column in index.columns) for index in table.indexes
    }
    assert {("user_id",), ("is_read",), ("created_at",)}.issubset(indexed_columns)

    ondelete_by_column = {
        next(iter(constraint.columns)).name: constraint.ondelete
        for constraint in table.foreign_key_constraints
    }
    assert ondelete_by_column["related_task_id"] == "SET NULL"
    assert ondelete_by_column["related_project_id"] == "SET NULL"
    assert ondelete_by_column["related_file_id"] == "SET NULL"


def test_notification_schedule_constraints_indexes_and_foreign_keys() -> None:
    table = Base.metadata.tables["notification_schedules"]
    indexed_columns = {
        tuple(column.name for column in index.columns) for index in table.indexes
    }
    assert {
        ("status", "scheduled_for"),
        ("task_id",),
        ("task_assignment_id",),
        ("user_id",),
    }.issubset(indexed_columns)

    unique_index_column_sets = {
        frozenset(column.name for column in index.columns)
        for index in table.indexes
        if index.unique
    }
    assert {
        frozenset(
            {"task_id", "user_id", "notification_type", "lead_time_minutes"}
        ),
        frozenset(
            {"task_assignment_id", "notification_type", "lead_time_minutes"}
        ),
    }.issubset(unique_index_column_sets)

    ondelete_by_column = {
        next(iter(constraint.columns)).name: constraint.ondelete
        for constraint in table.foreign_key_constraints
    }
    assert ondelete_by_column == {
        "user_id": "CASCADE",
        "task_id": "CASCADE",
        "task_assignment_id": "CASCADE",
        "sent_notification_id": "SET NULL",
    }


def test_task_assignment_indexes_and_cascade_foreign_keys() -> None:
    table = Base.metadata.tables["task_assignments"]
    indexed_columns = {
        tuple(column.name for column in index.columns) for index in table.indexes
    }
    assert {
        ("task_id",),
        ("user_id",),
        ("user_id", "status"),
    }.issubset(indexed_columns)

    ondelete_by_column = {
        next(iter(constraint.columns)).name: constraint.ondelete
        for constraint in table.foreign_key_constraints
    }
    assert ondelete_by_column == {"task_id": "CASCADE", "user_id": "CASCADE"}
