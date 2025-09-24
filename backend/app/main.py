from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from . import crud
from .database import get_session, init_db
from .models import (
    Benefit,
    BenefitFrequency,
    BenefitRedemption,
    BenefitType,
    CreditCard,
    YearTrackingMode,
)
from .schemas import (
    BenefitCreate,
    BenefitRedemptionCreate,
    BenefitRedemptionRead,
    BenefitRedemptionUpdate,
    BenefitRead,
    BenefitUpdate,
    BenefitUsageUpdate,
    CreditCardCreate,
    CreditCardUpdate,
    CreditCardWithBenefits,
    PreconfiguredCardRead,
    PreconfiguredCardWrite,
)
from .preconfigured import (
    create_preconfigured_card,
    delete_preconfigured_card,
    load_preconfigured_cards,
    update_preconfigured_card,
)

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


@app.post(
    "/api/admin/preconfigured/cards",
    response_model=PreconfiguredCardRead,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_preconfigured_card(payload: PreconfiguredCardWrite) -> PreconfiguredCardRead:
    return create_preconfigured_card(payload)


@app.put(
    "/api/admin/preconfigured/cards/{slug}",
    response_model=PreconfiguredCardRead,
)
def admin_update_preconfigured_card(
    slug: str, payload: PreconfiguredCardWrite
) -> PreconfiguredCardRead:
    try:
        return update_preconfigured_card(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preconfigured card not found",
        ) from exc
    except FileExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A card with the provided slug already exists.",
        ) from exc


@app.delete(
    "/api/admin/preconfigured/cards/{slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def admin_delete_preconfigured_card(slug: str) -> Response:
    try:
        delete_preconfigured_card(slug)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preconfigured card not found",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    return build_enriched_benefit(session, benefit, card)


@app.put("/api/benefits/{benefit_id}", response_model=BenefitRead)
def update_benefit(
    benefit_id: int, payload: BenefitUpdate, session: Session = Depends(get_session)
) -> BenefitRead:
    benefit = require_benefit(session, benefit_id)
    updated = crud.update_benefit(session, benefit, payload)
    return build_enriched_benefit(session, updated)


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
    return build_enriched_benefit(session, updated)


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


@app.put(
    "/api/redemptions/{redemption_id}",
    response_model=BenefitRedemptionRead,
)
def update_benefit_redemption(
    redemption_id: int,
    payload: BenefitRedemptionUpdate,
    session: Session = Depends(get_session),
) -> BenefitRedemptionRead:
    redemption = require_redemption(session, redemption_id)
    updated = crud.update_benefit_redemption(session, redemption, payload)
    return BenefitRedemptionRead.model_validate(updated, from_attributes=True)


@app.delete(
    "/api/redemptions/{redemption_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_benefit_redemption(
    redemption_id: int, session: Session = Depends(get_session)
) -> Response:
    redemption = require_redemption(session, redemption_id)
    crud.delete_benefit_redemption(session, redemption)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    metrics = gather_benefit_metrics(session, card, raw_benefits)
    overall_totals = metrics["overall"]
    cycle_totals = metrics["cycle"]
    window_totals = metrics["window_totals"]
    window_info = metrics["window_info"]
    cycle_label = metrics["cycle_label"]

    benefits: List[BenefitRead] = []
    for benefit in raw_benefits:
        frequency = benefit.frequency
        summary = overall_totals.get(benefit.id)
        cycle_total = cycle_totals.get(benefit.id, (0.0, 0))[0]
        info = window_info.get(frequency, {})
        window_label = info.get("label") or cycle_label
        frequency_totals = window_totals.get(frequency, {})
        window_entry = frequency_totals.get(benefit.id)
        if frequency == BenefitFrequency.yearly:
            current_window_total = cycle_total
        else:
            current_window_total = window_entry[0] if window_entry else 0.0
        benefits.append(
            build_benefit_read(
                benefit,
                summary,
                cycle_total,
                cycle_label,
                current_window_total,
                window_label,
            )
        )

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


def require_redemption(session: Session, redemption_id: int) -> BenefitRedemption:
    redemption = crud.get_benefit_redemption(session, redemption_id)
    if not redemption:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Redemption not found",
        )
    return redemption

def _safe_day(year: int, month: int, day: int) -> int:
    _, last_day = calendar.monthrange(year, month)
    return min(day, last_day)


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = _safe_day(year, month, value.day)
    return date(year, month, day)


def _compute_card_cycle_bounds(
    card: CreditCard, reference: date | None = None
) -> Tuple[date, date]:
    today = reference or date.today()
    if card.year_tracking_mode == YearTrackingMode.anniversary:
        due_month = card.fee_due_date.month
        due_day = card.fee_due_date.day
        cycle_end = date(today.year, due_month, _safe_day(today.year, due_month, due_day))
        if cycle_end <= today:
            cycle_end = date(
                today.year + 1, due_month, _safe_day(today.year + 1, due_month, due_day)
            )
        cycle_start = date(
            cycle_end.year - 1,
            due_month,
            _safe_day(cycle_end.year - 1, due_month, due_day),
        )
    else:
        cycle_start = date(today.year, 1, 1)
        cycle_end = date(today.year + 1, 1, 1)
    return cycle_start, cycle_end


def _format_cycle_label(card: CreditCard, cycle_start: date, cycle_end: date) -> str:
    if card.year_tracking_mode == YearTrackingMode.calendar:
        return str(cycle_start.year)
    inclusive_end = cycle_end - timedelta(days=1)
    return f"{cycle_start.year}-{inclusive_end.year}"


def _format_range_label(window_start: date, window_end: date) -> str:
    inclusive_end = window_end - timedelta(days=1)
    start_label = f"{window_start.strftime('%b')} {window_start.day}"
    end_label = f"{inclusive_end.strftime('%b')} {inclusive_end.day}"
    if window_start.year == inclusive_end.year:
        return f"{start_label} – {end_label}"
    return f"{start_label} {window_start.year} – {end_label} {inclusive_end.year}"


def _window_prefix(frequency: BenefitFrequency, index: int) -> str:
    if frequency == BenefitFrequency.monthly:
        return f"Month {index}"
    if frequency == BenefitFrequency.quarterly:
        return f"Quarter {index}"
    if frequency == BenefitFrequency.semiannual:
        return f"Half {index}"
    return "Year"


def _current_frequency_window(
    cycle_start: date,
    cycle_end: date,
    frequency: BenefitFrequency,
    reference: date | None = None,
) -> Tuple[date, date, str, int]:
    reference_date = reference or date.today()
    months_map = {
        BenefitFrequency.monthly: 1,
        BenefitFrequency.quarterly: 3,
        BenefitFrequency.semiannual: 6,
        BenefitFrequency.yearly: 12,
    }
    months = months_map.get(frequency)
    if not months:
        label = f"{_window_prefix(frequency, 1)} · {_format_range_label(cycle_start, cycle_end)}"
        return cycle_start, cycle_end, label, 1
    windows: List[Tuple[date, date, str, int]] = []
    index = 1
    cursor = cycle_start
    while cursor < cycle_end:
        window_end = _add_months(cursor, months)
        if window_end > cycle_end:
            window_end = cycle_end
        label = f"{_window_prefix(frequency, index)} · {_format_range_label(cursor, window_end)}"
        windows.append((cursor, window_end, label, index))
        cursor = window_end
        index += 1
    if not windows:
        label = f"{_window_prefix(frequency, 1)} · {_format_range_label(cycle_start, cycle_end)}"
        return cycle_start, cycle_end, label, 1
    for window_start, window_end, label, idx in windows:
        if window_start <= reference_date < window_end:
            return window_start, window_end, label, idx
    return windows[-1]


def gather_benefit_metrics(
    session: Session, card: CreditCard, benefits: List[Benefit]
) -> Dict[str, object]:
    benefit_ids = [benefit.id for benefit in benefits if benefit.id is not None]
    cycle_start, cycle_end = _compute_card_cycle_bounds(card)
    cycle_label = _format_cycle_label(card, cycle_start, cycle_end)
    overall_totals = crud.redemption_summary_for_benefits(session, benefit_ids)
    cycle_totals = crud.redemption_summary_for_benefits(
        session, benefit_ids, cycle_start, cycle_end
    )
    frequency_groups: Dict[BenefitFrequency, List[int]] = {}
    for benefit in benefits:
        frequency_groups.setdefault(benefit.frequency, []).append(benefit.id)
    window_totals: Dict[BenefitFrequency, Dict[int, Tuple[float, int]]] = {}
    window_info: Dict[BenefitFrequency, Dict[str, object]] = {}
    for frequency in BenefitFrequency:
        window_start, window_end, label, _ = _current_frequency_window(
            cycle_start, cycle_end, frequency
        )
        window_info[frequency] = {
            "start": window_start,
            "end": window_end,
            "label": label,
        }
        ids = frequency_groups.get(frequency, [])
        if ids and window_start < window_end:
            window_totals[frequency] = crud.redemption_summary_for_benefits(
                session, ids, window_start, window_end
            )
        else:
            window_totals[frequency] = {}
    return {
        "overall": overall_totals,
        "cycle": cycle_totals,
        "window_totals": window_totals,
        "window_info": window_info,
        "cycle_label": cycle_label,
    }


def build_enriched_benefit(
    session: Session, benefit: Benefit, card: CreditCard | None = None
) -> BenefitRead:
    parent_card = card or require_card(session, benefit.credit_card_id)
    metrics = gather_benefit_metrics(session, parent_card, [benefit])
    summary = metrics["overall"].get(benefit.id)
    cycle_total = metrics["cycle"].get(benefit.id, (0.0, 0))[0]
    frequency = benefit.frequency
    info = metrics["window_info"].get(frequency, {})
    window_label = info.get("label") or metrics["cycle_label"]
    window_entry = metrics["window_totals"].get(frequency, {}).get(benefit.id)
    if frequency == BenefitFrequency.yearly:
        current_window_total = cycle_total
    else:
        current_window_total = window_entry[0] if window_entry else 0.0
    return build_benefit_read(
        benefit,
        summary,
        cycle_total,
        metrics["cycle_label"],
        current_window_total,
        window_label,
    )


def build_benefit_read(
    benefit: Benefit,
    redemption_summary: Tuple[float, int] | None,
    cycle_total: float,
    cycle_label: str,
    window_total: float | None,
    window_label: Optional[str],
) -> BenefitRead:
    total, count = redemption_summary or (0.0, 0)
    cycle_value = float(cycle_total)
    window_value = float(window_total) if window_total is not None else None
    remaining: Optional[float]
    if benefit.type == BenefitType.incremental:
        target = float(benefit.value or 0)
        remaining = max(target - cycle_value, 0)
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
        expected_value=benefit.expected_value,
        expiration_date=benefit.expiration_date,
        is_used=benefit.is_used,
        used_at=benefit.used_at,
        redemption_total=total,
        redemption_count=count,
        remaining_value=remaining,
        cycle_redemption_total=cycle_value,
        cycle_label=cycle_label,
        current_window_total=window_value,
        current_window_label=window_label,
    )


def compute_benefit_totals(benefit: BenefitRead) -> Tuple[float, float]:
    cycle_total = float(benefit.cycle_redemption_total or 0)
    if benefit.type == BenefitType.standard:
        potential = float(benefit.value or 0)
        utilized = potential if benefit.is_used else 0.0
    elif benefit.type == BenefitType.incremental:
        potential = float(benefit.value or 0)
        utilized = min(cycle_total, potential)
    else:
        potential = float(benefit.expected_value or cycle_total)
        utilized = min(cycle_total, potential) if benefit.expected_value else cycle_total
    return potential, utilized
