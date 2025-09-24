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


def get_session() -> Iterator[Session]:
    """Yield a database session for dependency injection."""

    with Session(engine) as session:
        yield session
