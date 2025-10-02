"""API smoke tests that mirror the Vue pages loaded in Codex previews."""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.app.models import YearTrackingMode

from .factories import (
    add_benefit_set,
    create_card,
    reset_database,
    seed_backup_settings,
    seed_notification_history,
    seed_notification_settings,
)
from .shared import FREQUENCIES


def test_dashboard_page_loads_with_mock_cards(
    engine,
    session_factory: sessionmaker,
    client: TestClient,
    freeze_today,
) -> None:
    reset_database(engine)
    card = create_card(
        session_factory,
        name="Dashboard Preview",
        card_mode=YearTrackingMode.calendar,
    )
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
    assert payload and payload[0]["card_name"] == "Dashboard Preview"
    assert payload[0]["benefits"], "Expected seeded benefits for dashboard preview"


def test_benefits_page_loads_supporting_data(
    engine,
    session_factory: sessionmaker,
    client: TestClient,
    freeze_today,
) -> None:
    reset_database(engine)
    card = create_card(
        session_factory,
        name="Benefits Preview",
        card_mode=YearTrackingMode.anniversary,
    )
    add_benefit_set(
        session_factory,
        card,
        suffix="Anniversary Cycle",
        window_mode=None,
        redemption_date=freeze_today,
    )

    cards_response = client.get("/api/cards")
    assert cards_response.status_code == 200
    cards_payload = cards_response.json()
    assert cards_payload and cards_payload[0]["card_name"] == "Benefits Preview"

    frequencies_response = client.get("/api/frequencies")
    assert frequencies_response.status_code == 200
    assert set(frequencies_response.json()) == {freq.value for freq in FREQUENCIES}


def test_benefits_analysis_page_loads_redemption_history(
    engine,
    session_factory: sessionmaker,
    client: TestClient,
    freeze_today,
) -> None:
    reset_database(engine)
    card = create_card(
        session_factory,
        name="Analysis Preview",
        card_mode=YearTrackingMode.calendar,
    )
    add_benefit_set(
        session_factory,
        card,
        suffix="Calendar Cycle",
        window_mode=None,
        redemption_date=freeze_today,
    )

    cards_response = client.get("/api/cards")
    assert cards_response.status_code == 200
    cards_payload = cards_response.json()
    benefit_id = cards_payload[0]["benefits"][0]["id"]

    history_response = client.get(f"/api/benefits/{benefit_id}/redemptions")
    assert history_response.status_code == 200
    entries = history_response.json()
    assert entries, "Expected at least one redemption for analysis preview"
    assert entries[0]["amount"] == 25.0


def test_admin_page_loads_configuration_endpoints(
    engine,
    session_factory: sessionmaker,
    client: TestClient,
) -> None:
    reset_database(engine)
    seed_notification_settings(session_factory)
    seed_backup_settings(
        session_factory,
        last_success=datetime(2024, 5, 18, 8, 30, 0),
    )

    interface_response = client.get("/api/interface/settings")
    assert interface_response.status_code == 200
    interface_payload = interface_response.json()
    assert interface_payload["id"] == 1

    notifications_response = client.get("/api/admin/notifications/settings")
    assert notifications_response.status_code == 200
    notifications_payload = notifications_response.json()
    assert notifications_payload["base_url"].startswith("https://example.home-assistant")

    backup_response = client.get("/api/admin/backup/settings")
    assert backup_response.status_code == 200
    backup_payload = backup_response.json()
    assert backup_payload["server"] == "192.0.2.10"
    assert backup_payload["has_password"] is True

    preconfigured_response = client.get("/api/preconfigured/cards")
    assert preconfigured_response.status_code == 200
    assert isinstance(preconfigured_response.json(), list)


def test_notifications_page_loads_history(
    engine,
    session_factory: sessionmaker,
    client: TestClient,
) -> None:
    reset_database(engine)
    seed_notification_settings(session_factory)
    seed_notification_history(session_factory, response_message="accepted")

    history_response = client.get("/api/admin/notifications/history")
    assert history_response.status_code == 200
    entries = history_response.json()
    assert entries, "Expected seeded notification history entries"
    first_entry = entries[0]
    assert first_entry["event_type"] == "daily"
    assert first_entry["response_message"] == "accepted"

