from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func
from sqlmodel import Session, select

from .models import Benefit, BenefitRedemption, BenefitType, CreditCard
from .schemas import (
    BenefitCreate,
    BenefitRedemptionCreate,
    BenefitRedemptionUpdate,
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
    data = payload.model_dump()
    value = data.pop("value", None)
    benefit = Benefit(
        **data,
        credit_card_id=card.id,
        value=value if value is not None else 0,
    )
    session.add(benefit)
    session.commit()
    session.refresh(benefit)
    sync_incremental_usage_status(session, benefit)
    return benefit


def update_benefit(session: Session, benefit: Benefit, payload: BenefitUpdate) -> Benefit:
    update_data = payload.model_dump(exclude_unset=True)
    value = update_data.pop("value", None)
    is_used = update_data.pop("is_used", None)
    expected_value = update_data.pop("expected_value", None)
    new_type = update_data.get("type")

    if new_type and new_type != benefit.type:
        benefit.is_used = False
        benefit.used_at = None
        if new_type != BenefitType.cumulative:
            benefit.expected_value = None

    for key, item in update_data.items():
        setattr(benefit, key, item)

    if value is not None:
        benefit.value = value

    if "expected_value" in payload.model_fields_set:
        benefit.expected_value = expected_value

    if is_used is not None and benefit.type == BenefitType.standard:
        benefit.is_used = is_used
        benefit.used_at = datetime.utcnow() if is_used else None

    session.add(benefit)
    session.commit()
    session.refresh(benefit)
    sync_incremental_usage_status(session, benefit)
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


def create_benefit_redemption(
    session: Session, benefit: Benefit, payload: BenefitRedemptionCreate
) -> BenefitRedemption:
    redemption = BenefitRedemption(
        **payload.model_dump(),
        benefit_id=benefit.id,
    )
    session.add(redemption)
    session.commit()
    session.refresh(redemption)
    sync_incremental_usage_status(session, benefit)
    return redemption


def get_benefit_redemption(
    session: Session, redemption_id: int
) -> Optional[BenefitRedemption]:
    return session.get(BenefitRedemption, redemption_id)


def update_benefit_redemption(
    session: Session, redemption: BenefitRedemption, payload: BenefitRedemptionUpdate
) -> BenefitRedemption:
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(redemption, key, value)
    session.add(redemption)
    session.commit()
    session.refresh(redemption)
    sync_incremental_usage_status(session, redemption.benefit_id)
    return redemption


def delete_benefit_redemption(session: Session, redemption: BenefitRedemption) -> None:
    benefit_id = redemption.benefit_id
    session.delete(redemption)
    session.commit()
    sync_incremental_usage_status(session, benefit_id)


def list_benefit_redemptions(session: Session, benefit_id: int) -> List[BenefitRedemption]:
    statement = (
        select(BenefitRedemption)
        .where(BenefitRedemption.benefit_id == benefit_id)
        .order_by(BenefitRedemption.occurred_on.desc(), BenefitRedemption.id.desc())
    )
    return session.exec(statement).all()


def redemption_summary_for_benefits(
    session: Session,
    benefit_ids: Sequence[int],
    start_date: date | None = None,
    end_date: date | None = None,
) -> Dict[int, Tuple[float, int]]:
    if not benefit_ids:
        return {}
    statement = (
        select(
            BenefitRedemption.benefit_id,
            func.coalesce(func.sum(BenefitRedemption.amount), 0),
            func.count(BenefitRedemption.id),
        )
        .where(BenefitRedemption.benefit_id.in_(benefit_ids))
        .group_by(BenefitRedemption.benefit_id)
    )
    if start_date is not None:
        statement = statement.where(BenefitRedemption.occurred_on >= start_date)
    if end_date is not None:
        statement = statement.where(BenefitRedemption.occurred_on < end_date)
    results = session.exec(statement).all()
    return {benefit_id: (float(total), int(count)) for benefit_id, total, count in results}


def sync_incremental_usage_status(session: Session, benefit: Benefit | int) -> None:
    if isinstance(benefit, int):
        benefit_obj = session.get(Benefit, benefit)
    else:
        benefit_obj = benefit
    if not benefit_obj or benefit_obj.type != BenefitType.incremental:
        return

    totals = redemption_summary_for_benefits(session, [benefit_obj.id])
    total_amount = totals.get(benefit_obj.id, (0.0, 0))[0]
    should_be_used = benefit_obj.value > 0 and total_amount >= benefit_obj.value
    if benefit_obj.is_used != should_be_used:
        benefit_obj.is_used = should_be_used
        benefit_obj.used_at = datetime.utcnow() if should_be_used else None
        session.add(benefit_obj)
        session.commit()
        session.refresh(benefit_obj)
