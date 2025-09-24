from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel

from .models import BenefitFrequency


class BenefitBase(SQLModel):
    name: str
    description: Optional[str] = None
    frequency: BenefitFrequency
    value: float = Field(ge=0)
    expiration_date: Optional[date] = None


class BenefitCreate(BenefitBase):
    pass


class BenefitUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    frequency: Optional[BenefitFrequency] = None
    value: Optional[float] = Field(default=None, ge=0)
    expiration_date: Optional[date] = None
    is_used: Optional[bool] = None


class BenefitUsageUpdate(SQLModel):
    is_used: bool


class BenefitRead(BenefitBase):
    id: int
    credit_card_id: int
    is_used: bool
    used_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CreditCardBase(SQLModel):
    card_name: str
    last_four: str = Field(min_length=4, max_length=4)
    account_name: str
    annual_fee: float = Field(ge=0)
    fee_due_date: date


class CreditCardCreate(CreditCardBase):
    pass


class CreditCardUpdate(SQLModel):
    card_name: Optional[str] = None
    last_four: Optional[str] = Field(default=None, min_length=4, max_length=4)
    account_name: Optional[str] = None
    annual_fee: Optional[float] = Field(default=None, ge=0)
    fee_due_date: Optional[date] = None


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
