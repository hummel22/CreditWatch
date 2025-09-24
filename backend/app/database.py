from __future__ import annotations

from pathlib import Path
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

DATABASE_PATH = Path(__file__).resolve().parents[1] / "data"
DATABASE_PATH.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATABASE_PATH / 'creditwatch.db'}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    """Create database tables if they do not already exist."""

    SQLModel.metadata.create_all(engine)
    ensure_company_name_column()
    ensure_benefit_type_column()
    ensure_benefit_window_values_column()
    ensure_card_year_tracking_column()


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
