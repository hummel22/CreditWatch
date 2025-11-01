"""Integration tests validating benefit window metrics across tracking modes."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.app import crud, main
from backend.app.main import _compute_cycle_bounds, _format_cycle_label_for_mode
from backend.app.models import BenefitFrequency, BenefitType, CreditCard, YearTrackingMode
from backend.app.schemas import (
    BenefitCreate,
    BenefitRedemptionCreate,
    BenefitUpdate,
)

from .factories import add_benefit_set, create_card, reset_database
from .shared import FREQUENCIES, WINDOW_COUNT_BY_FREQUENCY


def _freeze_today(monkeypatch: pytest.MonkeyPatch, target: date) -> None:
    class FrozenDate(date):
        @classmethod
        def today(cls) -> date:  # type: ignore[override]
            return target

    class FrozenDateTime(datetime):
        @classmethod
        def utcnow(cls) -> datetime:  # type: ignore[override]
            return datetime.combine(target, datetime.min.time())

    monkeypatch.setattr(main, "date", FrozenDate)
    monkeypatch.setattr(crud, "date", FrozenDate)
    monkeypatch.setattr(crud, "datetime", FrozenDateTime)


def _expected_cycle_label(
    session_factory: sessionmaker,
    card_id: int,
    mode: YearTrackingMode,
) -> str:
    with session_factory() as session:
        card = session.get(CreditCard, card_id)
        assert card is not None
    start, end = _compute_cycle_bounds(card, mode)
    return _format_cycle_label_for_mode(mode, start, end)


@pytest.mark.parametrize(
    "card_name, card_mode, override_mode, default_suffix, override_suffix",
    [
        (
            "Anniversary Rewards",
            YearTrackingMode.anniversary,
            YearTrackingMode.calendar,
            "Anniversary Cycle",
            "Calendar Override",
        ),
        (
            "Calendar Rewards",
            YearTrackingMode.calendar,
            YearTrackingMode.anniversary,
            "Calendar Cycle",
            "Anniversary Override",
        ),
    ],
)
def test_benefit_windows_cover_all_tracking_modes(
    engine,
    session_factory: sessionmaker,
    client: TestClient,
    freeze_today: date,
    card_name: str,
    card_mode: YearTrackingMode,
    override_mode: YearTrackingMode,
    default_suffix: str,
    override_suffix: str,
) -> None:
    reset_database(engine)
    card = create_card(session_factory, name=card_name, card_mode=card_mode)
    add_benefit_set(
        session_factory,
        card,
        suffix=default_suffix,
        window_mode=None,
        redemption_date=freeze_today,
    )
    add_benefit_set(
        session_factory,
        card,
        suffix=override_suffix,
        window_mode=override_mode,
        redemption_date=freeze_today,
    )

    default_cycle_label = _expected_cycle_label(session_factory, card.id, card_mode)
    override_cycle_label = _expected_cycle_label(session_factory, card.id, override_mode)

    response = client.get("/api/cards")
    assert response.status_code == 200
    cards = response.json()
    assert len(cards) == 1
    card_payload = cards[0]

    assert card_payload["card_name"] == card_name
    assert len(card_payload["benefits"]) == len(BenefitType) * len(FREQUENCIES) * 2

    benefit_counts = Counter()
    for benefit in card_payload["benefits"]:
        benefit_counts[(benefit["type"], benefit["frequency"], benefit["window_tracking_mode"])] += 1
        expected_cycle = (
            override_cycle_label
            if benefit["window_tracking_mode"] is not None
            else default_cycle_label
        )
        assert benefit["cycle_label"] == expected_cycle
        expected_windows = WINDOW_COUNT_BY_FREQUENCY[benefit["frequency"]]
        assert benefit["cycle_window_count"] == expected_windows
        assert benefit["current_window_label"]
        assert 0 <= benefit["current_window_total"] <= 25.0
    for benefit_type in BenefitType:
        for frequency in FREQUENCIES:
            key_default = (benefit_type.value, frequency.value, None)
            key_override = (benefit_type.value, frequency.value, override_mode.value)
            assert benefit_counts[key_default] == 1
            assert benefit_counts[key_override] == 1


def test_benefit_windows_endpoint_returns_sorted_names(
    engine,
    session_factory: sessionmaker,
    client: TestClient,
    freeze_today: date,
) -> None:
    reset_database(engine)
    card = create_card(session_factory, name="Preview Card", card_mode=YearTrackingMode.calendar)
    add_benefit_set(
        session_factory,
        card,
        suffix="Calendar Cycle",
        window_mode=None,
        redemption_date=freeze_today,
    )

    response = client.get("/api/cards")
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["card_name"] == "Preview Card"
    names = [benefit["name"] for benefit in payload[0]["benefits"]]
    expected_names = {
        f"{benefit_type.value.title()} {frequency.value.title()} - Calendar Cycle"
        for benefit_type in BenefitType
        for frequency in FREQUENCIES
    }
    assert set(names) == expected_names
    frequencies = {benefit["frequency"] for benefit in payload[0]["benefits"]}
    assert frequencies == {freq.value for freq in FREQUENCIES}


@pytest.mark.parametrize(
    "benefit_type",
    [BenefitType.standard, BenefitType.incremental],
)
def test_manual_completion_persists_after_sync(
    engine,
    session_factory: sessionmaker,
    benefit_type: BenefitType,
) -> None:
    """Manual completion toggles should not be reset by usage sync."""

    reset_database(engine)
    card = create_card(
        session_factory,
        name="Manual Completion Card",
        card_mode=YearTrackingMode.calendar,
    )

    with session_factory() as session:
        persistent_card = session.get(CreditCard, card.id)
        assert persistent_card is not None
        benefit = crud.create_benefit(
            session,
            persistent_card,
            BenefitCreate(
                name="Manual Completion Benefit",
                description="",
                frequency=BenefitFrequency.monthly,
                type=benefit_type,
                value=120.0,
            ),
        )
        session.refresh(benefit)
        updated = crud.update_benefit(
            session,
            benefit,
            BenefitUpdate(is_used=True),
        )
        session.refresh(updated)

    assert updated.is_used is True


def test_incremental_completion_resets_with_new_window(
    engine,
    session_factory: sessionmaker,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incremental usage should reset once the next window begins."""

    reset_database(engine)
    card = create_card(
        session_factory,
        name="Rolling Window Card",
        card_mode=YearTrackingMode.calendar,
    )

    with session_factory() as session:
        persistent_card = session.get(CreditCard, card.id)
        assert persistent_card is not None
        _freeze_today(monkeypatch, date(2024, 10, 15))
        benefit = crud.create_benefit(
            session,
            persistent_card,
            BenefitCreate(
                name="Streaming Credit",
                description="",
                frequency=BenefitFrequency.monthly,
                type=BenefitType.incremental,
                value=20.0,
            ),
        )
        session.refresh(benefit)

        crud.create_benefit_redemption(
            session,
            benefit,
            BenefitRedemptionCreate(
                label="Dinner",
                amount=20.0,
                occurred_on=date(2024, 10, 5),
            ),
        )
        session.refresh(benefit)
        assert benefit.is_used is True

    _freeze_today(monkeypatch, date(2024, 11, 1))

    response = client.get("/api/cards")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    benefits = payload[0]["benefits"]
    assert len(benefits) == 1
    benefit_payload = benefits[0]
    assert benefit_payload["name"] == "Streaming Credit"
    assert benefit_payload["is_used"] is False
    assert benefit_payload["current_window_total"] == pytest.approx(0.0)


@pytest.mark.parametrize(
    "frequency, benefit_type, redemption_date, evaluation_date",
    [
        pytest.param(
            BenefitFrequency.monthly,
            BenefitType.standard,
            date(2024, 10, 5),
            date(2024, 11, 1),
            id="standard-monthly",
        ),
        pytest.param(
            BenefitFrequency.monthly,
            BenefitType.incremental,
            date(2024, 10, 5),
            date(2024, 11, 1),
            id="incremental-monthly",
        ),
        pytest.param(
            BenefitFrequency.quarterly,
            BenefitType.standard,
            date(2024, 5, 15),
            date(2024, 7, 1),
            id="standard-quarterly",
        ),
        pytest.param(
            BenefitFrequency.quarterly,
            BenefitType.incremental,
            date(2024, 5, 15),
            date(2024, 7, 1),
            id="incremental-quarterly",
        ),
        pytest.param(
            BenefitFrequency.semiannual,
            BenefitType.standard,
            date(2024, 3, 10),
            date(2024, 7, 1),
            id="standard-semiannual",
        ),
        pytest.param(
            BenefitFrequency.semiannual,
            BenefitType.incremental,
            date(2024, 3, 10),
            date(2024, 7, 1),
            id="incremental-semiannual",
        ),
    ],
)
def test_transaction_completion_remains_in_origin_window(
    engine,
    session_factory: sessionmaker,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    frequency: BenefitFrequency,
    benefit_type: BenefitType,
    redemption_date: date,
    evaluation_date: date,
) -> None:
    """Automatic completion only applies to the window containing the redemption."""

    reset_database(engine)
    card = create_card(
        session_factory,
        name="Window Confinement Card",
        card_mode=YearTrackingMode.calendar,
    )

    benefit_id: int
    redemption_amount = 50.0 if benefit_type == BenefitType.incremental else 25.0

    with session_factory() as session:
        persistent_card = session.get(CreditCard, card.id)
        assert persistent_card is not None
        benefit = crud.create_benefit(
            session,
            persistent_card,
            BenefitCreate(
                name=f"{benefit_type.value.title()} {frequency.value.title()} Window",
                description="",
                frequency=frequency,
                type=benefit_type,
                value=redemption_amount,
            ),
        )
        session.refresh(benefit)
        assert benefit.id is not None
        benefit_id = benefit.id

        _freeze_today(monkeypatch, redemption_date)
        crud.create_benefit_redemption(
            session,
            benefit,
            BenefitRedemptionCreate(
                label="Qualifying purchase",
                amount=redemption_amount,
                occurred_on=redemption_date,
            ),
        )
        session.refresh(benefit)
        assert benefit.is_used is True

    _freeze_today(monkeypatch, redemption_date)
    response = client.get("/api/cards")
    assert response.status_code == 200
    benefits = response.json()[0]["benefits"]
    origin_payload = next(item for item in benefits if item["id"] == benefit_id)
    assert origin_payload["is_used"] is True
    assert origin_payload["current_window_total"] == pytest.approx(redemption_amount)

    _freeze_today(monkeypatch, evaluation_date)
    response = client.get("/api/cards")
    assert response.status_code == 200
    benefits = response.json()[0]["benefits"]
    next_window_payload = next(item for item in benefits if item["id"] == benefit_id)
    assert next_window_payload["is_used"] is False
    assert next_window_payload["current_window_total"] == pytest.approx(0.0)


def test_incremental_manual_completion_after_prior_window_activity(
    engine,
    session_factory: sessionmaker,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manual toggles should still mark the active window complete after prior redemptions."""

    reset_database(engine)
    first_window_date = date(2024, 10, 12)
    second_window_date = date(2024, 11, 3)

    card = create_card(
        session_factory,
        name="Manual Incremental Override",
        card_mode=YearTrackingMode.calendar,
    )

    benefit_id: int

    with session_factory() as session:
        persistent_card = session.get(CreditCard, card.id)
        assert persistent_card is not None
        _freeze_today(monkeypatch, first_window_date)
        benefit = crud.create_benefit(
            session,
            persistent_card,
            BenefitCreate(
                name="Quarterly Dining Credit",
                description="",
                frequency=BenefitFrequency.monthly,
                type=BenefitType.incremental,
                value=50.0,
                window_values=[50.0] * 12,
            ),
        )
        session.refresh(benefit)
        assert benefit.id is not None
        benefit_id = benefit.id

        crud.create_benefit_redemption(
            session,
            benefit,
            BenefitRedemptionCreate(
                label="October dining", amount=50.0, occurred_on=first_window_date
            ),
        )
        session.refresh(benefit)
        assert benefit.is_used is True

    _freeze_today(monkeypatch, second_window_date)
    response = client.get("/api/cards")
    assert response.status_code == 200
    cards = response.json()
    assert cards
    benefits = cards[0]["benefits"]
    payload = next(item for item in benefits if item["id"] == benefit_id)
    assert payload["is_used"] is False
    assert payload["current_window_total"] == pytest.approx(0.0)

    with session_factory() as session:
        benefit = crud.get_benefit(session, benefit_id)
        assert benefit is not None
        benefit.is_used = True
        benefit.used_at = datetime.combine(second_window_date, datetime.min.time())
        session.add(benefit)
        session.commit()

    response = client.get("/api/cards")
    assert response.status_code == 200
    cards = response.json()
    assert cards
    benefits = cards[0]["benefits"]
    payload = next(item for item in benefits if item["id"] == benefit_id)
    assert payload["is_used"] is True
    assert payload["current_window_total"] == pytest.approx(0.0)


def test_recurring_expiration_rolls_forward(
    engine,
    session_factory: sessionmaker,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recurring benefits should surface the current window expiration date."""

    reset_database(engine)
    target_today = date(2025, 10, 29)

    class FrozenDate(date):
        @classmethod
        def today(cls) -> date:
            return target_today

    monkeypatch.setattr(main, "date", FrozenDate)
    monkeypatch.setattr(crud, "date", FrozenDate)

    card = create_card(
        session_factory,
        name="Expiration Drift Card",
        card_mode=YearTrackingMode.calendar,
    )

    with session_factory() as session:
        persistent_card = session.get(CreditCard, card.id)
        assert persistent_card is not None
        benefit = crud.create_benefit(
            session,
            persistent_card,
            BenefitCreate(
                name="Monthly Streaming Credit",
                description="",
                frequency=BenefitFrequency.monthly,
                type=BenefitType.standard,
                value=15.0,
                expiration_date=date(2025, 9, 30),
            ),
        )
        session.refresh(benefit)
        benefit_id = benefit.id

    response = client.get("/api/cards")
    assert response.status_code == 200
    cards = response.json()
    assert cards
    benefits = cards[0]["benefits"]
    payload = next(item for item in benefits if item["id"] == benefit_id)

    assert payload["expiration_date"] == "2025-10-31"
