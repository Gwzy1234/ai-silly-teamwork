from importlib import util
from pathlib import Path
from types import ModuleType

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect

from silly_teamwork.db.base import Base

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "migrations"
    / "versions"
    / "20260815_0009_add_notification_schedules.py"
)


def _load_migration() -> ModuleType:
    spec = util.spec_from_file_location("notification_schedule_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_notification_schedule_migration_up_down_up(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'notification-schedule-migration.db'}")
    existing_tables = [
        table
        for table_name, table in Base.metadata.tables.items()
        if table_name != "notification_schedules"
    ]
    migration = _load_migration()

    with engine.begin() as connection:
        Base.metadata.create_all(connection, tables=existing_tables)
        context = MigrationContext.configure(connection)

        with Operations.context(context):
            migration.upgrade()
        assert "notification_schedules" in inspect(connection).get_table_names()

        with Operations.context(context):
            migration.downgrade()
        assert "notification_schedules" not in inspect(connection).get_table_names()

        with Operations.context(context):
            migration.upgrade()
        assert "notification_schedules" in inspect(connection).get_table_names()

    engine.dispose()
