from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from backend.app.models import YearTrackingMode

from .factories import reset_database


def _create_card(client: TestClient) -> dict[str, object]:
    payload = {
        "card_name": "Test Card",
        "company_name": "Test Issuer",
        "last_four": "1234",
        "account_name": "Primary",
        "annual_fee": 95.0,
        "fee_due_date": date(2025, 7, 15).isoformat(),
        "year_tracking_mode": YearTrackingMode.calendar.value,
        "is_cancelled": False,
    }
    response = client.post("/api/cards", json=payload)
    assert response.status_code == 201
    return response.json()


def test_card_creation_seeds_annual_fee_history(
    engine, client: TestClient
) -> None:
    reset_database(engine)
    card = _create_card(client)

    summary_response = client.get(f"/api/cards/{card['id']}/annual-fees")
    assert summary_response.status_code == 200
    summary = summary_response.json()

    assert summary["card_id"] == card["id"]
    assert summary["current_annual_fee"] == card["annual_fee"]
    assert summary["future_annual_fee"] == card["annual_fee"]
    current_year = int(card["fee_due_date"].split("-")[0])
    history_years = {entry["year"]: entry["annual_fee"] for entry in summary["history"]}
    assert history_years[current_year] == card["annual_fee"]


def test_update_future_annual_fee(engine, client: TestClient) -> None:
    reset_database(engine)
    card = _create_card(client)

    response = client.put(
        f"/api/cards/{card['id']}/annual-fees/future",
        json={"annual_fee": 150.0},
    )
    assert response.status_code == 200
    summary = response.json()

    assert summary["future_annual_fee"] == 150.0
    assert summary["current_annual_fee"] == card["annual_fee"]

    cards_response = client.get("/api/cards")
    assert cards_response.status_code == 200
    cards = cards_response.json()
    assert cards[0]["future_annual_fee"] == 150.0
    assert cards[0]["annual_fee"] == card["annual_fee"]


def test_update_annual_fee_history(engine, client: TestClient) -> None:
    reset_database(engine)
    card = _create_card(client)
    current_year = int(card["fee_due_date"].split("-")[0])

    update_response = client.put(
        f"/api/cards/{card['id']}/annual-fees/{current_year}",
        json={"annual_fee": 75.0},
    )
    assert update_response.status_code == 200
    summary = update_response.json()

    assert summary["current_annual_fee"] == 75.0
    history_years = {entry["year"]: entry["annual_fee"] for entry in summary["history"]}
    assert history_years[current_year] == 75.0

    cards_response = client.get("/api/cards")
    assert cards_response.status_code == 200
    cards = cards_response.json()
    assert cards[0]["annual_fee"] == 75.0

    next_year = current_year + 1
    future_update = client.put(
        f"/api/cards/{card['id']}/annual-fees/{next_year}",
        json={"annual_fee": 155.0},
    )
    assert future_update.status_code == 200
    future_summary = future_update.json()
    history_years = {entry["year"]: entry["annual_fee"] for entry in future_summary["history"]}
    assert history_years[next_year] == 155.0
    assert future_summary["future_annual_fee"] == summary["future_annual_fee"]
