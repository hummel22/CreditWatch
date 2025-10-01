"""Lightweight database migration runner."""

from __future__ import annotations

import logging
from typing import Callable, Iterable, List, Sequence

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


MIGRATIONS: Sequence[tuple[str, MigrationFunc]] = (
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
        with engine.begin() as connection:
            migration(connection)
            _record_migration(connection, name)
        applied.add(name)

