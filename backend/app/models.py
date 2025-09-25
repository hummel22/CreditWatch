from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import List, Optional

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
    expiration_date: Optional[date] = None
    is_used: bool = Field(default=False)
    used_at: Optional[datetime] = None


class BenefitRedemption(SQLModel, table=True):
    """Individual redemption or usage entry for a benefit."""

    id: Optional[int] = Field(default=None, primary_key=True)
    benefit_id: int = Field(foreign_key="benefit.id", index=True)
    label: str
    amount: float = Field(ge=0)
    occurred_on: date = Field(default_factory=date.today)
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BackupSettings(SQLModel, table=True):
    """Configuration required to upload database backups to Google Drive."""

    id: Optional[int] = Field(default=1, primary_key=True)
    drive_folder_id: str = Field(description="Target Google Drive folder identifier")
    service_account_json: str = Field(
        description="Raw JSON credentials for the Google service account",
    )
    service_account_email: Optional[str] = Field(
        default=None,
        description="Derived service account email for display purposes",
    )
    last_backup_at: Optional[datetime] = Field(default=None)
    last_backup_file_id: Optional[str] = Field(default=None)
    last_backup_filename: Optional[str] = Field(default=None)
    last_backup_size: Optional[int] = Field(default=None, ge=0)
    last_backup_error: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_configured(self) -> bool:
        return bool(self.drive_folder_id and self.service_account_json)

