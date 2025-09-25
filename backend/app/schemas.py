from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional, Sequence

from pydantic import ConfigDict, field_validator, model_validator
from sqlmodel import Field, SQLModel

from .models import BenefitFrequency, BenefitType, YearTrackingMode


WINDOW_COUNT_BY_FREQUENCY: dict[BenefitFrequency, int] = {
    BenefitFrequency.monthly: 12,
    BenefitFrequency.quarterly: 4,
    BenefitFrequency.semiannual: 2,
}


def normalise_window_values(
    frequency: BenefitFrequency, values: Optional[Sequence[float | int | None]]
) -> Optional[List[float]]:
    """Validate and serialise per-window values for a benefit."""

    if values is None:
        return None
    cleaned = [value for value in values if value is not None]
    if not cleaned:
        return None
    expected = WINDOW_COUNT_BY_FREQUENCY.get(frequency)
    if expected is None:
        raise ValueError(
            "Custom window values are only supported for monthly, quarterly, or semiannual benefits."
        )
    if len(cleaned) != expected:
        raise ValueError(
            f"Expected {expected} values for a {frequency.value} benefit, received {len(cleaned)}."
        )
    serialised: List[float] = []
    for index, raw in enumerate(cleaned, start=1):
        try:
            number = float(raw)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive guard
            raise ValueError(
                f"Window value #{index} for {frequency.value} benefits must be numeric."
            ) from exc
        if number < 0:
            raise ValueError("Window values must be zero or greater.")
        serialised.append(number)
    return serialised


class BenefitBase(SQLModel):
    name: str
    description: Optional[str] = None
    frequency: BenefitFrequency
    type: BenefitType = Field(default=BenefitType.standard)
    value: Optional[float] = Field(default=None, ge=0)
    expected_value: Optional[float] = Field(default=None, ge=0)
    expiration_date: Optional[date] = None
    window_values: Optional[List[float]] = None


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
        if values.window_values is not None:
            values.window_values = normalise_window_values(values.frequency, values.window_values)
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
    window_values: Optional[List[float]] = None

    @model_validator(mode="after")
    def validate_window_values(
        cls, values: "BenefitUpdate"
    ) -> "BenefitUpdate":  # type: ignore[name-defined]
        if values.frequency is not None and values.window_values is not None:
            values.window_values = normalise_window_values(
                values.frequency, values.window_values
            )
        return values


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
    cycle_redemption_total: float = Field(default=0, ge=0)
    cycle_label: Optional[str] = None
    current_window_total: Optional[float] = Field(default=None, ge=0)
    current_window_label: Optional[str] = None
    current_window_value: Optional[float] = Field(default=None, ge=0)
    current_window_index: Optional[int] = Field(default=None, ge=1)
    cycle_window_count: Optional[int] = Field(default=None, ge=1)
    cycle_target_value: Optional[float] = Field(default=None, ge=0)

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
    last_four: str = Field(min_length=4, max_length=5)
    account_name: str
    annual_fee: float = Field(ge=0)
    fee_due_date: date
    year_tracking_mode: YearTrackingMode = Field(default=YearTrackingMode.calendar)


class CreditCardCreate(CreditCardBase):
    pass


class CreditCardUpdate(SQLModel):
    card_name: Optional[str] = None
    company_name: Optional[str] = None
    last_four: Optional[str] = Field(default=None, min_length=4, max_length=5)
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


class NotificationSettingsBase(SQLModel):
    base_url: str
    webhook_id: str
    default_target: Optional[str] = None
    enabled: bool = True

    @field_validator("base_url")
    @classmethod
    def normalise_base_url(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("A Home Assistant URL is required.")
        if not cleaned.startswith("http://") and not cleaned.startswith("https://"):
            raise ValueError("The Home Assistant URL must start with http:// or https://.")
        return cleaned.rstrip("/")


class NotificationSettingsRead(NotificationSettingsBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationSettingsWrite(NotificationSettingsBase):
    pass


class NotificationSettingsUpdate(SQLModel):
    base_url: Optional[str] = None
    webhook_id: Optional[str] = None
    default_target: Optional[str] = None
    enabled: Optional[bool] = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned.startswith("http://") and not cleaned.startswith("https://"):
            raise ValueError("The Home Assistant URL must start with http:// or https://.")
        return cleaned.rstrip("/")


class NotificationCustomMessage(SQLModel):
    message: str
    title: Optional[str] = None
    target_override: Optional[str] = None


class NotificationDailyTestRequest(SQLModel):
    target_date: date
    target_override: Optional[str] = None


class NotificationBenefitSummary(SQLModel):
    card_name: str
    benefit_name: str
    expiration_date: date


class NotificationDispatchResult(SQLModel):
    sent: bool
    message: Optional[str] = None
    categories: Dict[str, List[NotificationBenefitSummary]] = Field(default_factory=dict)


class PreconfiguredBenefitBase(SQLModel):
    name: str
    description: Optional[str] = None
    frequency: BenefitFrequency
    type: BenefitType = Field(default=BenefitType.standard)
    value: Optional[float] = Field(default=None, ge=0)
    expected_value: Optional[float] = Field(default=None, ge=0)
    window_values: Optional[List[float]] = None


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
        if values.window_values is not None:
            values.window_values = normalise_window_values(values.frequency, values.window_values)
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

