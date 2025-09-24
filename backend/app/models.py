from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

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


class CreditCard(SQLModel, table=True):
    """Credit card stored in the system."""

    id: Optional[int] = Field(default=None, primary_key=True)
    card_name: str = Field(index=True)
    company_name: str = Field(
        default="",
        index=True,
        description="Card issuer or bank name",
    )
    last_four: str = Field(min_length=4, max_length=4, description="Last four digits")
    account_name: str = Field(index=True, description="Account holder or user account identifier")
    annual_fee: float = Field(ge=0)
    fee_due_date: date
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

