from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class BenefitFrequency(str, Enum):
    """Frequency of a benefit reset cycle."""

    monthly = "monthly"
    quarterly = "quarterly"
    semiannual = "semiannual"
    yearly = "yearly"


class BenefitType(str, Enum):
    """Different tracking behaviours for a benefit."""

    standard = "standard"
    incremental = "incremental"
    cumulative = "cumulative"


class YearTrackingMode(str, Enum):
    """How a card groups activity across years for history calculations."""

    calendar = "calendar"
    anniversary = "anniversary"


class ThemeMode(str, Enum):
    """Supported interface theme variants."""

    light = "light"
    dark = "dark"


class CreditCard(SQLModel, table=True):
    """Credit card stored in the system."""

    id: Optional[int] = Field(default=None, primary_key=True)
    card_name: str = Field(index=True)
    company_name: str = Field(
        default="",
        index=True,
        description="Card issuer or bank name",
    )
    last_four: str = Field(
        min_length=4,
        max_length=5,
        description="Last four or five digits",
    )
    account_name: str = Field(index=True, description="Account holder or user account identifier")
    annual_fee: float = Field(ge=0)
    fee_due_date: date
    year_tracking_mode: YearTrackingMode = Field(
        default=YearTrackingMode.calendar,
        description="How the card's history windows are calculated",
    )
    is_cancelled: bool = Field(
        default=False,
        description="Whether the card has been cancelled and should trigger reminders",
    )
    cancelled_at: Optional[datetime] = Field(
        default=None,
        description="When the card was marked as cancelled",
    )
    display_order: Optional[int] = Field(
        default=None,
        index=True,
        description="Order used when presenting cards in the dashboard",
        ge=0,
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Benefit(SQLModel, table=True):
    """Benefit associated with a credit card."""

    id: Optional[int] = Field(default=None, primary_key=True)
    credit_card_id: int = Field(foreign_key="creditcard.id", index=True)
    name: str
    description: Optional[str] = None
    frequency: BenefitFrequency
    type: BenefitType = Field(default=BenefitType.standard)
    value: float = Field(default=0, ge=0)
    expected_value: Optional[float] = Field(default=None, ge=0)
    window_values: Optional[List[float]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    window_tracking_mode: Optional[YearTrackingMode] = Field(default=None)
    expiration_date: Optional[date] = None
    is_used: bool = Field(default=False)
    used_at: Optional[datetime] = None
    exclude_from_benefits_page: bool = Field(
        default=False,
        description="Whether the benefit should be hidden from the aggregated benefits page",
    )
    exclude_from_notifications: bool = Field(
        default=False,
        description="Whether the benefit should be excluded from notification digests",
    )


class BenefitRedemption(SQLModel, table=True):
    """Individual redemption or usage entry for a benefit."""

    id: Optional[int] = Field(default=None, primary_key=True)
    benefit_id: int = Field(foreign_key="benefit.id", index=True)
    label: str
    amount: float = Field(ge=0)
    occurred_on: date = Field(default_factory=date.today)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class BenefitWindowExclusion(SQLModel, table=True):
    """Windows that should be excluded from benefit calculations."""

    id: Optional[int] = Field(default=None, primary_key=True)
    benefit_id: int = Field(foreign_key="benefit.id", index=True)
    window_start: date = Field(index=True)
    window_end: date
    window_label: Optional[str] = None
    window_index: Optional[int] = Field(default=None, ge=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class NotificationSettings(SQLModel, table=True):
    """Connection settings for the Home Assistant notification webhook."""

    id: Optional[int] = Field(default=1, primary_key=True)
    base_url: str = Field(description="Base URL for the Home Assistant instance")
    webhook_id: str = Field(description="Webhook identifier configured in Home Assistant")
    default_target: Optional[str] = Field(
        default=None,
        description="Optional default target slug understood by the Home Assistant automation",
    )
    enabled: bool = Field(default=True, description="Whether notifications are currently enabled")
    event_type_preferences: Dict[str, bool] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, default=dict),
        description=(
            "Per-notification-type enablement overrides stored as a JSON mapping "
            "of event type to boolean."
        ),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BackupSettings(SQLModel, table=True):
    """Configuration for automated SMB database backups."""

    id: Optional[int] = Field(default=1, primary_key=True)
    server: str = Field(description="Hostname or IP address of the SMB server")
    share: str = Field(description="Share name that will store database backups")
    directory: str = Field(
        default="",
        description="Optional subdirectory within the share for database backups",
    )
    username: str = Field(description="SMB account used to authenticate")
    password: str = Field(description="SMB account password")
    domain: Optional[str] = Field(
        default=None,
        description="Optional domain or workgroup for authentication",
    )
    last_backup_at: Optional[datetime] = None
    last_backup_filename: Optional[str] = None
    last_backup_error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class NotificationLog(SQLModel, table=True):
    """Historical record of notification dispatch attempts."""

    id: Optional[int] = Field(default=None, primary_key=True)
    event_type: str = Field(index=True, description="Type of notification that was triggered")
    title: Optional[str] = Field(default=None, description="Title sent to Home Assistant")
    body: Optional[str] = Field(default=None, description="Body content sent to Home Assistant")
    target: Optional[str] = Field(default=None, description="Notification target used for delivery")
    sent: bool = Field(default=False, description="Whether the webhook call was successful")
    response_message: Optional[str] = Field(
        default=None, description="Human readable outcome message from the dispatcher"
    )
    reason: Optional[str] = Field(
        default=None,
        description="Explanation of why the notification ran or was skipped",
    )
    categories: Dict[str, object] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, default=dict),
        description="Summary payload that accompanied the notification",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class Bug(SQLModel, table=True):
    """Simple bug tracker entry."""

    id: Optional[int] = Field(default=None, primary_key=True)
    description: str = Field(description="Bug summary or reproduction details")
    is_completed: bool = Field(default=False, description="Whether the bug has been resolved")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(
        default=None, description="When the bug was marked complete"
    )


class InterfaceSettings(SQLModel, table=True):
    """Global interface preferences shared across the application."""

    id: Optional[int] = Field(default=1, primary_key=True)
    theme_mode: ThemeMode = Field(
        default=ThemeMode.light,
        description="Preferred UI theme for all users",
    )

