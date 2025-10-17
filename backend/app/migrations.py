"""Lightweight database migration runner."""

from __future__ import annotations

import logging
from typing import Callable, Sequence

from sqlalchemy.engine import Connection, Engine

logger = logging.getLogger("creditwatch.migrations")


MigrationFunc = Callable[[Connection], None]


def _ensure_migrations_table(connection: Connection) -> None:
    """Create the schema migrations tracking table if required."""

    connection.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _get_applied_migrations(connection: Connection) -> set[str]:
    """Return the set of migration identifiers that have already run."""

    rows = connection.exec_driver_sql("SELECT name FROM schema_migrations")
    return {str(row[0]) for row in rows}


def _record_migration(connection: Connection, name: str) -> None:
    """Mark a migration as applied in the tracking table."""

    connection.exec_driver_sql(
        "INSERT INTO schema_migrations (name) VALUES (?)",
        (name,),
    )


def _list_tables(connection: Connection) -> set[str]:
    """Return the set of tables present in the database."""

    rows = connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _get_table_columns(connection: Connection, table: str) -> set[str]:
    """Return the set of column names for ``table`` if it exists."""

    rows = connection.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return {str(row[1]) for row in rows}


_EXPECTED_MIGRATION_SCHEMAS: dict[str, dict[str, set[str]]] = {
    "2024101201_create_interface_settings": {
        "interfacesettings": {"id", "theme_mode"},
    },
    "2024100301_add_notification_reason_and_preferences": {
        "notificationlog": {"reason"},
        "notificationsettings": {"event_type_preferences"},
    },
}


def _log_schema_comparison(connection: Connection, migration_name: str) -> None:
    """Log the differences between expected and actual schema for a migration."""

    expectations = _EXPECTED_MIGRATION_SCHEMAS.get(migration_name)
    if not expectations:
        logger.debug(
            "No schema expectations registered for migration %s", migration_name
        )
        return

    tables = _list_tables(connection)
    for table_name, expected_columns in expectations.items():
        if table_name not in tables:
            logger.error(
                "Migration %s expects table %s but it was not found. Existing tables: %s",
                migration_name,
                table_name,
                sorted(tables),
            )
            continue

        actual_columns = _get_table_columns(connection, table_name)
        missing = expected_columns - actual_columns
        if missing:
            logger.error(
                "Migration %s missing columns for %s: %s (actual columns: %s)",
                migration_name,
                table_name,
                sorted(missing),
                sorted(actual_columns),
            )
        else:
            logger.info(
                "Migration %s verified required columns %s.%s (actual columns: %s)",
                migration_name,
                table_name,
                sorted(expected_columns),
                sorted(actual_columns),
            )


def _add_notification_reason_and_preferences(connection: Connection) -> None:
    """Add audit fields for notification history and preferences."""

    existing_log_columns = {
        row[1]
        for row in connection.exec_driver_sql("PRAGMA table_info(notificationlog)")
    }
    if "reason" not in existing_log_columns:
        logger.info("Adding notificationlog.reason column")
        connection.exec_driver_sql(
            "ALTER TABLE notificationlog ADD COLUMN reason VARCHAR"
        )

    existing_settings_columns = {
        row[1]
        for row in connection.exec_driver_sql("PRAGMA table_info(notificationsettings)")
    }
    if "event_type_preferences" not in existing_settings_columns:
        logger.info("Adding notificationsettings.event_type_preferences column")
        connection.exec_driver_sql(
            """
            ALTER TABLE notificationsettings
            ADD COLUMN event_type_preferences JSON NOT NULL DEFAULT '{}'
            """
        )
        connection.exec_driver_sql(
            """
            UPDATE notificationsettings
            SET event_type_preferences='{}'
            WHERE event_type_preferences IS NULL
            """
        )


def _ensure_interface_settings(connection: Connection) -> None:
    """Create the interface settings table and default record if required."""

    tables = {
        row[0]
        for row in connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if "interfacesettings" not in tables:
        logger.info("Creating interfacesettings table")
        connection.exec_driver_sql(
            """
            CREATE TABLE interfacesettings (
                id INTEGER PRIMARY KEY,
                theme_mode VARCHAR NOT NULL DEFAULT 'light'
            )
            """
        )
    columns = {
        row[1]
        for row in connection.exec_driver_sql("PRAGMA table_info(interfacesettings)")
    }
    if "theme_mode" not in columns:
        logger.info("Adding interfacesettings.theme_mode column")
        connection.exec_driver_sql(
            "ALTER TABLE interfacesettings ADD COLUMN theme_mode VARCHAR NOT NULL DEFAULT 'light'"
        )
        connection.exec_driver_sql(
            "UPDATE interfacesettings SET theme_mode='light' WHERE theme_mode IS NULL"
        )
    rows = connection.exec_driver_sql("SELECT id FROM interfacesettings").fetchall()
    existing_ids = {row[0] for row in rows}
    if 1 not in existing_ids:
        logger.info("Seeding default interface settings row")
        connection.exec_driver_sql(
            "INSERT INTO interfacesettings (id, theme_mode) VALUES (1, 'light')"
        )


MIGRATIONS: Sequence[tuple[str, MigrationFunc]] = (
    ("2024101201_create_interface_settings", _ensure_interface_settings),
    ("2024100301_add_notification_reason_and_preferences", _add_notification_reason_and_preferences),
)


def run_migrations(engine: Engine) -> None:
    """Apply outstanding migrations in order."""

    if not MIGRATIONS:
        return

    with engine.begin() as connection:
        _ensure_migrations_table(connection)
        applied = _get_applied_migrations(connection)

    for name, migration in MIGRATIONS:
        if name in applied:
            continue
        logger.info("Applying migration %s", name)
        try:
            with engine.begin() as connection:
                migration(connection)
                _record_migration(connection, name)
        except Exception:
            logger.exception("Migration %s failed", name)
            with engine.begin() as connection:
                _log_schema_comparison(connection, name)
            raise
        applied.add(name)

    missing = [name for name, _ in MIGRATIONS if name not in applied]
    if missing:
        with engine.begin() as connection:
            for name in missing:
                logger.error("Migration %s did not complete", name)
                _log_schema_comparison(connection, name)
        raise RuntimeError(
            "Database migrations missing: " + ", ".join(missing)
        )

    with engine.begin() as connection:
        for name, _ in MIGRATIONS:
            _log_schema_comparison(connection, name)

