from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import logging
import os
import sqlite3

from filelock import FileLock, Timeout
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, SQLModel, create_engine

logger = logging.getLogger("creditwatch.database")


def _resolve_data_directory() -> Path:
    """Return the directory that should contain database artefacts."""

    env_path = os.getenv("CREDITWATCH_DATA_DIR")
    if env_path:
        directory = Path(env_path).expanduser()
        directory = directory.resolve(strict=False)
    else:
        directory = Path(__file__).resolve().parents[1] / "data"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _resolve_database_file(directory: Path) -> Path:
    env_file = os.getenv("CREDITWATCH_DB_FILE")
    if env_file:
        candidate = Path(env_file).expanduser()
        if not candidate.is_absolute():
            candidate = directory / candidate
    else:
        candidate = directory / "creditwatch.db"
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate.resolve(strict=False)


DATABASE_PATH = _resolve_data_directory()
DATABASE_FILE = _resolve_database_file(DATABASE_PATH)
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

_LOCK_FILENAME = f"{DATABASE_FILE.name}.init.lock"
_LOCK_PATH = DATABASE_FILE.parent / _LOCK_FILENAME
_LOCK_TIMEOUT = 60.0


def init_db() -> None:
    """Create database tables if they do not already exist."""

    logger.info("Initializing database at %s", DATABASE_FILE)
    with _database_initialisation_lock():
        _run_database_initialisation_steps()


def _run_database_initialisation_steps() -> None:
    """Perform the actual database initialisation work."""

    try:
        SQLModel.metadata.create_all(engine)
    except (OperationalError, sqlite3.OperationalError) as exc:
        _log_database_diagnostics(exc)
        raise
    ensure_company_name_column()
    ensure_benefit_type_column()
    ensure_benefit_window_values_column()
    ensure_benefit_window_tracking_column()
    ensure_benefit_visibility_column()
    ensure_card_year_tracking_column()


@contextmanager
def _database_initialisation_lock() -> Iterator[None]:
    """Serialise database initialisation across multiple workers."""

    lock = FileLock(str(_LOCK_PATH))
    try:
        lock.acquire(timeout=_LOCK_TIMEOUT)
        logger.debug("Acquired database initialisation lock at %s", _LOCK_PATH)
    except Timeout as exc:
        logger.error(
            "Timed out after %.0fs waiting for database initialisation lock %s",
            _LOCK_TIMEOUT,
            _LOCK_PATH,
        )
        raise RuntimeError("Could not acquire database initialisation lock") from exc
    try:
        yield
    finally:
        if lock.is_locked:
            lock.release()
            logger.debug("Released database initialisation lock at %s", _LOCK_PATH)


def _log_database_diagnostics(exc: Exception) -> None:
    """Log additional context about a database failure."""

    logger.error("Database initialisation failed: %s", exc)
    if not DATABASE_FILE.exists():
        logger.error("Database file %s does not exist", DATABASE_FILE)
    else:
        stat_info = DATABASE_FILE.stat()
        mode = oct(stat_info.st_mode & 0o777)
        logger.error("Database file permissions: mode=%s size=%s bytes", mode, stat_info.st_size)
        _log_permission_mismatch(stat_info.st_uid, stat_info.st_gid)
        readable = os.access(DATABASE_FILE, os.R_OK)
        writable = os.access(DATABASE_FILE, os.W_OK)
        logger.error(
            "Database accessibility: readable=%s writable=%s", readable, writable
        )
    directory = DATABASE_FILE.parent
    if not directory.exists():
        logger.error("Database directory %s does not exist", directory)
    else:
        if not os.access(directory, os.W_OK):
            logger.error("Database directory %s is not writable", directory)


def _log_permission_mismatch(owner_uid: int, owner_gid: int) -> None:
    """Log differences between the database owner and the running process."""

    current_uid = _safe_get_unix_credential("getuid")
    current_gid = _safe_get_unix_credential("getgid")
    if current_uid is not None and owner_uid != current_uid:
        logger.error(
            "Database owner UID (%s) does not match process UID (%s)",
            owner_uid,
            current_uid,
        )
    if current_gid is not None and owner_gid != current_gid:
        logger.error(
            "Database owner GID (%s) does not match process GID (%s)",
            owner_gid,
            current_gid,
        )


def _safe_get_unix_credential(attr: str) -> int | None:
    getter = getattr(os, attr, None)
    if getter is None:
        return None
    try:
        return getter()
    except OSError:
        return None


def ensure_company_name_column() -> None:
    """Backfill the ``company_name`` column for older databases."""

    with engine.connect() as connection:
        existing_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(creditcard)")
        }
        if "company_name" not in existing_columns:
            connection.exec_driver_sql(
                "ALTER TABLE creditcard ADD COLUMN company_name VARCHAR NOT NULL DEFAULT ''"
            )


def ensure_benefit_type_column() -> None:
    """Ensure benefit tables contain new tracking metadata columns."""

    with engine.connect() as connection:
        existing_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(benefit)")
        }
        if "type" not in existing_columns:
            connection.exec_driver_sql(
                "ALTER TABLE benefit ADD COLUMN type VARCHAR NOT NULL DEFAULT 'standard'"
            )
        if "value" not in existing_columns:
            connection.exec_driver_sql(
                "ALTER TABLE benefit ADD COLUMN value FLOAT NOT NULL DEFAULT 0"
            )
        if "expected_value" not in existing_columns:
            connection.exec_driver_sql(
                "ALTER TABLE benefit ADD COLUMN expected_value FLOAT"
            )


def ensure_benefit_window_values_column() -> None:
    """Ensure recurring benefits can store per-window values."""

    with engine.connect() as connection:
        existing_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(benefit)")
        }
        if "window_values" not in existing_columns:
            connection.exec_driver_sql(
                "ALTER TABLE benefit ADD COLUMN window_values JSON"
            )


def ensure_benefit_window_tracking_column() -> None:
    """Ensure benefits can override their window alignment."""

    with engine.connect() as connection:
        existing_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(benefit)")
        }
        if "window_tracking_mode" not in existing_columns:
            connection.exec_driver_sql(
                "ALTER TABLE benefit ADD COLUMN window_tracking_mode VARCHAR"
            )


def ensure_benefit_visibility_column() -> None:
    """Ensure benefits can be excluded from the aggregated benefits view."""

    with engine.connect() as connection:
        existing_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(benefit)")
        }
        if "exclude_from_benefits_page" not in existing_columns:
            connection.exec_driver_sql(
                "ALTER TABLE benefit ADD COLUMN exclude_from_benefits_page BOOLEAN NOT NULL DEFAULT 0"
            )


def ensure_card_year_tracking_column() -> None:
    """Ensure credit cards store the preferred year tracking mode."""

    with engine.connect() as connection:
        existing_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(creditcard)")
        }
        if "year_tracking_mode" not in existing_columns:
            connection.exec_driver_sql(
                "ALTER TABLE creditcard ADD COLUMN year_tracking_mode VARCHAR NOT NULL DEFAULT 'calendar'"
            )


def get_session() -> Iterator[Session]:
    """Yield a database session for dependency injection."""

    with Session(engine) as session:
        yield session
