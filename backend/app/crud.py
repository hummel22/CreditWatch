from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlmodel import Session, select

from .models import Benefit, CreditCard
from .schemas import (
    BenefitCreate,
    BenefitUpdate,
    BenefitUsageUpdate,
    CreditCardCreate,
    CreditCardUpdate,
)


def create_credit_card(session: Session, payload: CreditCardCreate) -> CreditCard:
    card = CreditCard(**payload.model_dump())
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


def update_credit_card(session: Session, card: CreditCard, payload: CreditCardUpdate) -> CreditCard:
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(card, key, value)
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


def delete_credit_card(session: Session, card: CreditCard) -> None:
    session.delete(card)
    session.commit()


def list_credit_cards(session: Session) -> List[CreditCard]:
    statement = select(CreditCard).order_by(CreditCard.created_at)
    return session.exec(statement).all()


def get_credit_card(session: Session, card_id: int) -> Optional[CreditCard]:
    return session.get(CreditCard, card_id)


def create_benefit(session: Session, card: CreditCard, payload: BenefitCreate) -> Benefit:
    benefit = Benefit(**payload.model_dump(), credit_card_id=card.id)
    session.add(benefit)
    session.commit()
    session.refresh(benefit)
    return benefit


def update_benefit(session: Session, benefit: Benefit, payload: BenefitUpdate) -> Benefit:
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(benefit, key, value)
    if update_data.get("is_used") is not None and update_data["is_used"]:
        benefit.used_at = benefit.used_at or datetime.utcnow()
    elif update_data.get("is_used") is not None and not update_data["is_used"]:
        benefit.used_at = None
    session.add(benefit)
    session.commit()
    session.refresh(benefit)
    return benefit


def set_benefit_usage(session: Session, benefit: Benefit, payload: BenefitUsageUpdate) -> Benefit:
    benefit.is_used = payload.is_used
    benefit.used_at = datetime.utcnow() if payload.is_used else None
    session.add(benefit)
    session.commit()
    session.refresh(benefit)
    return benefit


def get_benefit(session: Session, benefit_id: int) -> Optional[Benefit]:
    return session.get(Benefit, benefit_id)


def list_benefits_for_card(session: Session, card_id: int) -> List[Benefit]:
    statement = select(Benefit).where(Benefit.credit_card_id == card_id)
    return session.exec(statement).all()
