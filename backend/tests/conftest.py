"""Pytest fixtures shared across backend test modules."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
from typing import Iterable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app import main  # noqa: E402
from backend.app.main import app, get_session  # noqa: E402

from .shared import FROZEN_TODAY  # noqa: E402


@pytest.fixture(scope="module")
def engine() -> Iterable[object]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(scope="module")
def session_factory(engine) -> sessionmaker:
    return sessionmaker(bind=engine, class_=Session)


@pytest.fixture
def client(session_factory: sessionmaker) -> Iterable[TestClient]:
    def override_get_session() -> Iterable[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def freeze_today(monkeypatch: pytest.MonkeyPatch) -> date:
    class FrozenDate(date):
        @classmethod
        def today(cls) -> date:
            return cls(FROZEN_TODAY.year, FROZEN_TODAY.month, FROZEN_TODAY.day)

    monkeypatch.setattr(main, "date", FrozenDate)
    return FROZEN_TODAY

