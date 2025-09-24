from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import ConfigDict, model_validator
from sqlmodel import Field, SQLModel

from .models import BenefitFrequency, BenefitType, YearTrackingMode


class BenefitBase(SQLModel):
    name: str
    description: Optional[str] = None
    frequency: BenefitFrequency
    type: BenefitType = Field(default=BenefitType.standard)
    value: Optional[float] = Field(default=None, ge=0)
    expected_value: Optional[float] = Field(default=None, ge=0)
    expiration_date: Optional[date] = None


class BenefitCreate(BenefitBase):
    @model_validator(mode="after")
    def validate_value(cls, values: "BenefitCreate") -> "BenefitCreate":  # type: ignore[name-defined]
        if values.type != BenefitType.cumulative and (values.value is None or values.value <= 0):
            raise ValueError(
                "A positive value is required for standard and incremental benefits."
            )
        if values.type == BenefitType.cumulative and values.value not in (None, 0):
            raise ValueError("Cumulative benefits should not define an initial value.")
        if values.type != BenefitType.cumulative and values.expected_value not in (None, 0):
            raise ValueError("Expected value is only supported for cumulative benefits.")
        return values


class BenefitUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    frequency: Optional[BenefitFrequency] = None
    type: Optional[BenefitType] = None
    value: Optional[float] = Field(default=None, ge=0)
    expiration_date: Optional[date] = None
    is_used: Optional[bool] = None
    expected_value: Optional[float] = Field(default=None, ge=0)


class BenefitUsageUpdate(SQLModel):
    is_used: bool


class BenefitRead(BenefitBase):
    id: int
    credit_card_id: int
    value: float = Field(default=0, ge=0)
    is_used: bool
    used_at: Optional[datetime] = None
    redemption_total: float = Field(default=0, ge=0)
    redemption_count: int = Field(default=0, ge=0)
    remaining_value: Optional[float] = Field(default=None, ge=0)

    model_config = ConfigDict(from_attributes=True)


class BenefitRedemptionBase(SQLModel):
    label: str
    amount: float = Field(gt=0)
    occurred_on: date = Field(default_factory=date.today)


class BenefitRedemptionCreate(BenefitRedemptionBase):
    pass


class BenefitRedemptionRead(BenefitRedemptionBase):
    id: int
    benefit_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BenefitRedemptionUpdate(SQLModel):
    label: Optional[str] = None
    amount: Optional[float] = Field(default=None, gt=0)
    occurred_on: Optional[date] = None


class CreditCardBase(SQLModel):
    card_name: str
    company_name: str
    last_four: str = Field(min_length=4, max_length=4)
    account_name: str
    annual_fee: float = Field(ge=0)
    fee_due_date: date
    year_tracking_mode: YearTrackingMode = Field(default=YearTrackingMode.calendar)


class CreditCardCreate(CreditCardBase):
    pass


class CreditCardUpdate(SQLModel):
    card_name: Optional[str] = None
    company_name: Optional[str] = None
    last_four: Optional[str] = Field(default=None, min_length=4, max_length=4)
    account_name: Optional[str] = None
    annual_fee: Optional[float] = Field(default=None, ge=0)
    fee_due_date: Optional[date] = None
    year_tracking_mode: Optional[YearTrackingMode] = None


class CreditCardRead(CreditCardBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreditCardWithBenefits(CreditCardRead):
    benefits: List[BenefitRead]
    potential_value: float
    utilized_value: float
    net_position: float

    model_config = ConfigDict(from_attributes=True)


class PreconfiguredBenefitBase(SQLModel):
    name: str
    description: Optional[str] = None
    frequency: BenefitFrequency
    type: BenefitType = Field(default=BenefitType.standard)
    value: Optional[float] = Field(default=None, ge=0)
    expected_value: Optional[float] = Field(default=None, ge=0)


class PreconfiguredBenefitCreate(PreconfiguredBenefitBase):
    @model_validator(mode="after")
    def validate_value(
        cls, values: "PreconfiguredBenefitCreate"
    ) -> "PreconfiguredBenefitCreate":  # type: ignore[name-defined]
        if values.type != BenefitType.cumulative and (values.value is None or values.value <= 0):
            raise ValueError(
                "A positive value is required for standard and incremental benefits."
            )
        if values.type == BenefitType.cumulative and values.value not in (None, 0):
            raise ValueError("Cumulative benefits should not define an initial value.")
        if values.type != BenefitType.cumulative and values.expected_value not in (None, 0):
            raise ValueError("Expected value is only supported for cumulative benefits.")
        return values


class PreconfiguredBenefitRead(PreconfiguredBenefitBase):
    pass


class PreconfiguredCardBase(SQLModel):
    card_type: str
    company_name: str
    annual_fee: float = Field(ge=0)
    benefits: List[PreconfiguredBenefitCreate]


class PreconfiguredCardWrite(PreconfiguredCardBase):
    slug: Optional[str] = None


class PreconfiguredCardRead(SQLModel):
    slug: str
    card_type: str
    company_name: str
    annual_fee: float = Field(ge=0)
    benefits: List[PreconfiguredBenefitRead]

