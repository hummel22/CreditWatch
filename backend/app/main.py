from __future__ import annotations

from typing import List, Optional, Tuple

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from . import crud
from .database import get_session, init_db
from .models import Benefit, BenefitFrequency, BenefitType, CreditCard
from .schemas import (
    BenefitCreate,
    BenefitRedemptionCreate,
    BenefitRedemptionRead,
    BenefitRead,
    BenefitUpdate,
    BenefitUsageUpdate,
    CreditCardCreate,
    CreditCardUpdate,
    CreditCardWithBenefits,
    PreconfiguredCardRead,
)
from .preconfigured import load_preconfigured_cards

app = FastAPI(title="CreditWatch", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/frequencies", response_model=List[str])
def get_frequencies() -> List[str]:
    return [freq.value for freq in BenefitFrequency]


@app.get("/api/preconfigured/cards", response_model=List[PreconfiguredCardRead])
def get_preconfigured_cards() -> List[PreconfiguredCardRead]:
    return load_preconfigured_cards()


@app.get("/api/cards", response_model=List[CreditCardWithBenefits])
def list_cards(session: Session = Depends(get_session)) -> List[CreditCardWithBenefits]:
    cards = crud.list_credit_cards(session)
    return [build_card_response(session, card) for card in cards]


@app.post(
    "/api/cards",
    response_model=CreditCardWithBenefits,
    status_code=status.HTTP_201_CREATED,
)
def create_card(
    payload: CreditCardCreate, session: Session = Depends(get_session)
) -> CreditCardWithBenefits:
    card = crud.create_credit_card(session, payload)
    session.refresh(card)
    return build_card_response(session, card)


@app.put("/api/cards/{card_id}", response_model=CreditCardWithBenefits)
def update_card(
    card_id: int, payload: CreditCardUpdate, session: Session = Depends(get_session)
) -> CreditCardWithBenefits:
    card = require_card(session, card_id)
    updated = crud.update_credit_card(session, card, payload)
    return build_card_response(session, updated)


@app.delete(
    "/api/cards/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_card(card_id: int, session: Session = Depends(get_session)) -> Response:
    card = require_card(session, card_id)
    crud.delete_credit_card(session, card)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post(
    "/api/cards/{card_id}/benefits",
    response_model=BenefitRead,
    status_code=status.HTTP_201_CREATED,
)
def add_benefit(
    card_id: int, payload: BenefitCreate, session: Session = Depends(get_session)
) -> BenefitRead:
    card = require_card(session, card_id)
    benefit = crud.create_benefit(session, card, payload)
    session.refresh(benefit)
    return build_benefit_read(
        benefit, crud.redemption_summary_for_benefits(session, [benefit.id]).get(benefit.id)
    )


@app.put("/api/benefits/{benefit_id}", response_model=BenefitRead)
def update_benefit(
    benefit_id: int, payload: BenefitUpdate, session: Session = Depends(get_session)
) -> BenefitRead:
    benefit = require_benefit(session, benefit_id)
    updated = crud.update_benefit(session, benefit, payload)
    return build_benefit_read(
        updated,
        crud.redemption_summary_for_benefits(session, [updated.id]).get(updated.id),
    )


@app.post("/api/benefits/{benefit_id}/usage", response_model=BenefitRead)
def set_benefit_usage(
    benefit_id: int, payload: BenefitUsageUpdate, session: Session = Depends(get_session)
) -> BenefitRead:
    benefit = require_benefit(session, benefit_id)
    if benefit.type != BenefitType.standard:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usage toggles are only supported for standard benefits.",
        )
    updated = crud.set_benefit_usage(session, benefit, payload)
    return build_benefit_read(
        updated,
        crud.redemption_summary_for_benefits(session, [updated.id]).get(updated.id),
    )


@app.get(
    "/api/benefits/{benefit_id}/redemptions",
    response_model=List[BenefitRedemptionRead],
)
def list_benefit_redemptions(
    benefit_id: int, session: Session = Depends(get_session)
) -> List[BenefitRedemptionRead]:
    benefit = require_benefit(session, benefit_id)
    redemptions = crud.list_benefit_redemptions(session, benefit.id)
    return [
        BenefitRedemptionRead.model_validate(redemption, from_attributes=True)
        for redemption in redemptions
    ]


@app.post(
    "/api/benefits/{benefit_id}/redemptions",
    response_model=BenefitRedemptionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_benefit_redemption(
    benefit_id: int,
    payload: BenefitRedemptionCreate,
    session: Session = Depends(get_session),
) -> BenefitRedemptionRead:
    benefit = require_benefit(session, benefit_id)
    created = crud.create_benefit_redemption(session, benefit, payload)
    session.refresh(created)
    return BenefitRedemptionRead.model_validate(created, from_attributes=True)


@app.delete(
    "/api/benefits/{benefit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_benefit(benefit_id: int, session: Session = Depends(get_session)) -> Response:
    benefit = require_benefit(session, benefit_id)
    session.delete(benefit)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def build_card_response(session: Session, card: CreditCard) -> CreditCardWithBenefits:
    raw_benefits = crud.list_benefits_for_card(session, card.id)
    benefit_ids = [benefit.id for benefit in raw_benefits]
    redemption_summary = crud.redemption_summary_for_benefits(session, benefit_ids)
    benefits: List[BenefitRead] = [
        build_benefit_read(benefit, redemption_summary.get(benefit.id))
        for benefit in raw_benefits
    ]
    potential_value = 0.0
    utilized_value = 0.0
    for benefit in benefits:
        potential, utilized = compute_benefit_totals(benefit)
        potential_value += potential
        utilized_value += utilized
    return CreditCardWithBenefits(
        id=card.id,
        card_name=card.card_name,
        company_name=card.company_name,
        last_four=card.last_four,
        account_name=card.account_name,
        annual_fee=card.annual_fee,
        fee_due_date=card.fee_due_date,
        created_at=card.created_at,
        benefits=benefits,
        potential_value=potential_value,
        utilized_value=utilized_value,
        net_position=utilized_value - card.annual_fee,
    )


def require_card(session: Session, card_id: int) -> CreditCard:
    card = crud.get_credit_card(session, card_id)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    return card


def require_benefit(session: Session, benefit_id: int) -> Benefit:
    benefit = crud.get_benefit(session, benefit_id)
    if not benefit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Benefit not found"
        )
    return benefit


def build_benefit_read(
    benefit: Benefit, redemption_summary: Tuple[float, int] | None
) -> BenefitRead:
    total, count = redemption_summary or (0.0, 0)
    remaining: Optional[float]
    if benefit.type == BenefitType.incremental:
        remaining = max(benefit.value - total, 0)
    else:
        remaining = None
    return BenefitRead(
        id=benefit.id,
        credit_card_id=benefit.credit_card_id,
        name=benefit.name,
        description=benefit.description,
        frequency=benefit.frequency,
        type=benefit.type,
        value=benefit.value,
        expiration_date=benefit.expiration_date,
        is_used=benefit.is_used,
        used_at=benefit.used_at,
        redemption_total=total,
        redemption_count=count,
        remaining_value=remaining,
    )


def compute_benefit_totals(benefit: BenefitRead) -> Tuple[float, float]:
    if benefit.type == BenefitType.standard:
        potential = benefit.value
        utilized = benefit.value if benefit.is_used else 0.0
    elif benefit.type == BenefitType.incremental:
        potential = benefit.value
        utilized = min(benefit.redemption_total, benefit.value)
    else:
        potential = benefit.redemption_total
        utilized = benefit.redemption_total
    return potential, utilized
