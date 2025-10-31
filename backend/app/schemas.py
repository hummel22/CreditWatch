from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence

from pydantic import ConfigDict, field_validator, model_validator
from sqlmodel import Field, SQLModel

from .models import BenefitFrequency, BenefitType, ThemeMode, YearTrackingMode


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


class BugBase(SQLModel):
    description: str

    @field_validator("description", mode="before")
    @classmethod
    def normalise_description(cls, value: Optional[str]) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise ValueError("Description is required.")
        return cleaned


class BugCreate(BugBase):
    pass


class BugUpdate(SQLModel):
    description: Optional[str] = None
    is_completed: Optional[bool] = None

    @field_validator("description", mode="before")
    @classmethod
    def trim_optional_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        if not cleaned:
            raise ValueError("Description cannot be empty.")
        return cleaned


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"false", "0", "no", "off", "disabled"}:
            return False
        if lowered in {"true", "1", "yes", "on", "enabled"}:
            return True
    return bool(value)


def normalise_event_type_preferences(value: Optional[Any]) -> Dict[str, bool]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Event type preferences must be an object.")
    cleaned: Dict[str, bool] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        enabled = _coerce_bool(raw_value)
        if enabled:
            continue
        cleaned[key] = False
    return cleaned


class BugRead(BugBase):
    id: int
    is_completed: bool
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class InterfaceSettingsBase(SQLModel):
    theme_mode: ThemeMode = Field(default=ThemeMode.light)


class InterfaceSettingsRead(InterfaceSettingsBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class InterfaceSettingsUpdate(SQLModel):
    theme_mode: ThemeMode


class BenefitBase(SQLModel):
    name: str
    description: Optional[str] = None
    frequency: BenefitFrequency
    type: BenefitType = Field(default=BenefitType.standard)
    value: Optional[float] = Field(default=None, ge=0)
    expected_value: Optional[float] = Field(default=None, ge=0)
    expiration_date: Optional[date] = None
    window_values: Optional[List[float]] = None
    window_tracking_mode: Optional[YearTrackingMode] = None
    exclude_from_benefits_page: bool = Field(default=False)
    exclude_from_notifications: bool = Field(default=False)


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
    window_tracking_mode: Optional[YearTrackingMode] = None
    exclude_from_benefits_page: Optional[bool] = None
    exclude_from_notifications: Optional[bool] = None

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


class BenefitWindowExclusionBase(SQLModel):
    window_start: date
    window_end: date
    window_index: Optional[int] = Field(default=None, ge=1)
    window_label: Optional[str] = None

    @model_validator(mode="after")
    def validate_bounds(
        cls, values: "BenefitWindowExclusionBase"
    ) -> "BenefitWindowExclusionBase":  # type: ignore[name-defined]
        if values.window_end <= values.window_start:
            raise ValueError("Window end must be after the start date.")
        return values


class BenefitWindowExclusionCreate(BenefitWindowExclusionBase):
    pass


class BenefitWindowExclusionRead(BenefitWindowExclusionBase):
    id: int
    benefit_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
    missed_window_value: float = Field(default=0, ge=0)
    active_window_indexes: List[int] = Field(default_factory=list)
    window_exclusions: List[BenefitWindowExclusionRead] = Field(default_factory=list)
    current_window_deleted: bool = False

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
    is_cancelled: bool = Field(default=False)


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
    is_cancelled: Optional[bool] = None


class CreditCardRead(CreditCardBase):
    id: int
    created_at: datetime
    display_order: Optional[int] = None
    cancelled_at: Optional[datetime] = None
    future_annual_fee: float = Field(ge=0)

    model_config = ConfigDict(from_attributes=True)


class CreditCardWithBenefits(CreditCardRead):
    benefits: List[BenefitRead]
    potential_value: float
    utilized_value: float
    net_position: float

    model_config = ConfigDict(from_attributes=True)


class CreditCardAnnualFeeHistoryEntry(SQLModel):
    year: int = Field(ge=1900)
    annual_fee: float = Field(ge=0)


class CreditCardAnnualFeeHistoryResponse(SQLModel):
    card_id: int
    current_year: int
    current_annual_fee: float = Field(ge=0)
    future_annual_fee: float = Field(ge=0)
    history: List[CreditCardAnnualFeeHistoryEntry] = Field(default_factory=list)


class CreditCardAnnualFeeUpdate(SQLModel):
    annual_fee: float = Field(ge=0)


class CreditCardReorderRequest(SQLModel):
    card_ids: List[int] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "CreditCardReorderRequest":
        if len(self.card_ids) != len(set(self.card_ids)):
            raise ValueError("Card order cannot contain duplicates.")
        return self


class NotificationSettingsBase(SQLModel):
    base_url: str
    webhook_id: str
    default_target: Optional[str] = None
    enabled: bool = True
    event_type_preferences: Dict[str, bool] = Field(default_factory=dict)

    @field_validator("base_url")
    @classmethod
    def normalise_base_url(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("A Home Assistant URL is required.")
        if not cleaned.startswith("http://") and not cleaned.startswith("https://"):
            raise ValueError("The Home Assistant URL must start with http:// or https://.")
        return cleaned.rstrip("/")

    @field_validator("event_type_preferences", mode="before")
    @classmethod
    def validate_event_type_preferences(cls, value: Optional[Any]) -> Dict[str, bool]:
        return normalise_event_type_preferences(value)


class NotificationSettingsRead(NotificationSettingsBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BackupSettingsBase(SQLModel):
    server: str
    share: str
    directory: str = Field(default="")
    username: str
    domain: Optional[str] = None

    @field_validator("server", "share", "username", mode="before")
    @classmethod
    def validate_required_field(cls, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise ValueError("This field cannot be empty.")
        return cleaned

    @field_validator("directory", mode="before")
    @classmethod
    def normalise_directory(cls, value: str) -> str:
        if value is None:
            return ""
        cleaned = str(value).strip().strip("/\\")
        return cleaned

    @field_validator("domain", mode="before")
    @classmethod
    def normalise_domain(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None


class BackupSettingsWrite(BackupSettingsBase):
    password: str

    @field_validator("password", mode="before")
    @classmethod
    def validate_password(cls, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise ValueError("Password is required.")
        return cleaned


class BackupSettingsUpdate(SQLModel):
    server: Optional[str] = None
    share: Optional[str] = None
    directory: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    domain: Optional[str] = None

    @field_validator("server", "share", "username", mode="before")
    @classmethod
    def trim_required_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        if not cleaned:
            raise ValueError("This field cannot be empty.")
        return cleaned

    @field_validator("password", mode="before")
    @classmethod
    def trim_password(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        if not cleaned:
            raise ValueError("Password cannot be empty.")
        return cleaned

    @field_validator("directory", mode="before")
    @classmethod
    def trim_directory(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip().strip("/\\")
        return cleaned

    @field_validator("domain", mode="before")
    @classmethod
    def trim_domain(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned if cleaned else None


class BackupSettingsRead(BackupSettingsBase):
    id: int
    last_backup_at: Optional[datetime] = None
    last_backup_filename: Optional[str] = None
    last_backup_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    next_backup_at: Optional[datetime] = None
    has_password: bool = False

    model_config = ConfigDict(from_attributes=True)


class BackupConnectionTestRequest(BackupSettingsBase):
    password: Optional[str] = None
    use_stored_password: bool = Field(default=False)

    @field_validator("password", mode="before")
    @classmethod
    def trim_optional_password(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None


class BackupConnectionTestResult(SQLModel):
    ok: bool
    detail: str


class NotificationSettingsWrite(NotificationSettingsBase):
    pass


class NotificationSettingsUpdate(SQLModel):
    base_url: Optional[str] = None
    webhook_id: Optional[str] = None
    default_target: Optional[str] = None
    enabled: Optional[bool] = None
    event_type_preferences: Optional[Dict[str, bool]] = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned.startswith("http://") and not cleaned.startswith("https://"):
            raise ValueError("The Home Assistant URL must start with http:// or https://.")
        return cleaned.rstrip("/")

    @field_validator("event_type_preferences", mode="before")
    @classmethod
    def validate_event_preferences_optional(
        cls, value: Optional[Any]
    ) -> Optional[Dict[str, bool]]:
        if value is None:
            return None
        return normalise_event_type_preferences(value)


class NotificationCustomMessage(SQLModel):
    message: str
    title: Optional[str] = None
    target_override: Optional[str] = None


class NotificationDailyTestRequest(SQLModel):
    target_date: date
    target_override: Optional[str] = None


class NotificationBenefitSummary(SQLModel):
    summary_type: str = Field(default="benefit")
    card_name: str
    benefit_name: str
    expiration_date: date


class NotificationCancelledCardSummary(SQLModel):
    summary_type: str = Field(default="cancelled_card")
    card_name: str
    account_name: Optional[str] = None
    company_name: Optional[str] = None
    fee_due_date: date
    days_until_due: int


class NotificationDispatchResult(SQLModel):
    sent: bool
    message: Optional[str] = None
    categories: Dict[
        str, List[NotificationBenefitSummary | NotificationCancelledCardSummary]
    ] = Field(default_factory=dict)
    target: Optional[str] = None


class NotificationLogRead(SQLModel):
    id: int
    event_type: str
    title: Optional[str] = None
    body: Optional[str] = None
    target: Optional[str] = None
    sent: bool
    response_message: Optional[str] = None
    reason: Optional[str] = None
    categories: Dict[
        str,
        List[NotificationBenefitSummary | NotificationCancelledCardSummary],
    ] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PreconfiguredBenefitBase(SQLModel):
    name: str
    description: Optional[str] = None
    frequency: BenefitFrequency
    type: BenefitType = Field(default=BenefitType.standard)
    value: Optional[float] = Field(default=None, ge=0)
    expected_value: Optional[float] = Field(default=None, ge=0)
    window_values: Optional[List[float]] = None
    window_tracking_mode: Optional[YearTrackingMode] = None
    exclude_from_benefits_page: bool = Field(default=False)
    exclude_from_notifications: bool = Field(default=False)


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


class CardTemplateExportRequest(SQLModel):
    slug: Optional[str] = None
    card_type: Optional[str] = None
    company_name: Optional[str] = None
    annual_fee: Optional[float] = Field(default=None, ge=0)
    override_existing: bool = Field(default=False)
    override_slug: Optional[str] = None

