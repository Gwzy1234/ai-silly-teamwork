from importlib import util
from pathlib import Path
from types import ModuleType

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect

from silly_teamwork.db.base import Base

MIGRATIONS_DIR = Path(__file__).parents[2] / "migrations" / "versions"


def _load_migration(filename: str, module_name: str) -> ModuleType:
    spec = util.spec_from_file_location(module_name, MIGRATIONS_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_notification_schedule_history_migration_up_down_up(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'schedule-history-migration.db'}")
    existing_tables = [
        table
        for table_name, table in Base.metadata.tables.items()
        if table_name != "notification_schedules"
    ]
    schedule_migration = _load_migration(
        "20260815_0009_add_notification_schedules.py",
        "notification_schedule_migration_for_history",
    )
    history_migration = _load_migration(
        "20260815_0010_allow_notification_schedule_history.py",
        "notification_schedule_history_migration",
    )

    with engine.begin() as connection:
        Base.metadata.create_all(connection, tables=existing_tables)
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            schedule_migration.upgrade()
            history_migration.upgrade()
        indexes = {
            item["name"]
            for item in inspect(connection).get_indexes("notification_schedules")
        }
        assert "uq_notification_schedules_active_task_user_type_lead" in indexes
        assert "uq_notification_schedules_active_assignment_type_lead" in indexes

        with Operations.context(context):
            history_migration.downgrade()
        unique_constraints = {
            item["name"]
            for item in inspect(connection).get_unique_constraints(
                "notification_schedules"
            )
        }
        assert "uq_notification_schedules_task_user_type_lead" in unique_constraints
        assert "uq_notification_schedules_assignment_type_lead" in unique_constraints

        with Operations.context(context):
            history_migration.upgrade()
        indexes = {
            item["name"]
            for item in inspect(connection).get_indexes("notification_schedules")
        }
        assert "uq_notification_schedules_active_task_user_type_lead" in indexes
        assert "uq_notification_schedules_active_assignment_type_lead" in indexes

    engine.dispose()
