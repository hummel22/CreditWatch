"""Factory helpers for seeding the in-memory database in tests."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from backend.app import crud
from backend.app.models import BenefitType, CreditCard, YearTrackingMode
from backend.app.schemas import (
    BackupSettingsWrite,
    BenefitCreate,
    BenefitRedemptionCreate,
    CreditCardCreate,
    NotificationSettingsWrite,
)

from .shared import FEE_DUE_DATE, FREQUENCIES, TYPE_VALUES


def reset_database(engine: Any) -> None:
    """Drop and recreate all tables for a clean test database."""

    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def create_card(
    session_factory: sessionmaker,
    *,
    name: str,
    card_mode: YearTrackingMode,
) -> CreditCard:
    """Persist a credit card using the CRUD layer and return it."""

    with session_factory() as session:
        card = crud.create_credit_card(
            session,
            CreditCardCreate(
                card_name=name,
                company_name="Test Issuer",
                last_four="0000",
                account_name="Primary",
                annual_fee=95.0,
                fee_due_date=FEE_DUE_DATE,
                year_tracking_mode=card_mode,
            ),
        )
        session.refresh(card)
        return card


def add_benefit_set(
    session_factory: sessionmaker,
    card: CreditCard,
    *,
    suffix: str,
    window_mode: YearTrackingMode | None,
    redemption_date: date,
) -> None:
    """Attach one benefit of each type/frequency combination to a card."""

    with session_factory() as session:
        persistent_card = session.get(CreditCard, card.id)
        assert persistent_card is not None
        for benefit_type in BenefitType:
            for frequency in FREQUENCIES:
                name = f"{benefit_type.value.title()} {frequency.value.title()} - {suffix}"
                payload_kwargs: dict[str, Any] = {
                    "name": name,
                    "description": f"{suffix} tracking for {frequency.value}",
                    "frequency": frequency,
                    "type": benefit_type,
                    "value": TYPE_VALUES[benefit_type],
                    "window_tracking_mode": window_mode,
                }
                if benefit_type == BenefitType.cumulative:
                    payload_kwargs["expected_value"] = 600.0
                benefit = crud.create_benefit(
                    session,
                    persistent_card,
                    BenefitCreate(**payload_kwargs),
                )
                if window_mode is not None and benefit_type == BenefitType.cumulative:
                    benefit.window_tracking_mode = window_mode
                    session.add(benefit)
                    session.commit()
                    session.refresh(benefit)
                crud.create_benefit_redemption(
                    session,
                    benefit,
                    BenefitRedemptionCreate(
                        label="Seed redemption",
                        amount=25.0,
                        occurred_on=redemption_date,
                    ),
                )


def seed_notification_settings(
    session_factory: sessionmaker,
    *,
    base_url: str = "https://example.home-assistant.invalid",
    webhook_id: str = "creditwatch-hook",
    default_target: str = "notify.mobile_app_primary",
    enabled: bool = True,
) -> None:
    """Create notification settings used by the admin view."""

    with session_factory() as session:
        crud.upsert_notification_settings(
            session,
            NotificationSettingsWrite(
                base_url=base_url,
                webhook_id=webhook_id,
                default_target=default_target,
                enabled=enabled,
            ),
        )


def seed_backup_settings(
    session_factory: sessionmaker,
    *,
    server: str = "192.0.2.10",
    share: str = "backups",
    directory: str = "creditwatch",
    username: str = "creditwatch",
    password: str = "s3cret",
    domain: str | None = None,
    last_success: datetime | None = None,
) -> None:
    """Populate backup settings for the admin view."""

    payload = BackupSettingsWrite(
        server=server,
        share=share,
        directory=directory,
        username=username,
        password=password,
        domain=domain or "",
    )
    with session_factory() as session:
        settings = crud.upsert_backup_settings(session, payload)
        if last_success is not None:
            crud.record_backup_success(
                session,
                settings,
                timestamp=last_success,
                filename="creditwatch-backup.zip",
            )


def seed_notification_history(
    session_factory: sessionmaker,
    *,
    event_type: str = "daily",
    title: str | None = "Daily summary",
    body: str | None = "1 benefit expiring soon",
    target: str | None = "notify.mobile_app_primary",
    sent: bool = True,
    response_message: str | None = "queued",
    reason: str | None = None,
    categories: dict[str, object] | None = None,
) -> None:
    """Insert a notification log entry for the notifications page."""

    with session_factory() as session:
        crud.log_notification_event(
            session,
            event_type=event_type,
            title=title,
            body=body,
            target=target,
            sent=sent,
            response_message=response_message,
            categories=categories,
            reason=reason,
        )

