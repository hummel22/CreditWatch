from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, or_
from sqlmodel import Session, select

from .models import (
    BackupSettings,
    Benefit,
    BenefitFrequency,
    BenefitRedemption,
    BenefitType,
    BenefitWindowExclusion,
    Bug,
    CreditCard,
    InterfaceSettings,
    NotificationLog,
    NotificationSettings,
    YearTrackingMode,
)
from .schemas import (
    BenefitCreate,
    BenefitRedemptionCreate,
    BenefitRedemptionUpdate,
    BenefitUpdate,
    BenefitUsageUpdate,
    BenefitWindowExclusionCreate,
    BugCreate,
    BugUpdate,
    CreditCardCreate,
    CreditCardUpdate,
    InterfaceSettingsUpdate,
    BackupSettingsUpdate,
    BackupSettingsWrite,
    NotificationSettingsUpdate,
    NotificationSettingsWrite,
)
from .schemas import normalise_window_values


def create_credit_card(session: Session, payload: CreditCardCreate) -> CreditCard:
    max_order_query = select(func.max(CreditCard.display_order))
    max_order_result = session.exec(max_order_query).one()
    if isinstance(max_order_result, tuple):
        max_order_result = max_order_result[0]
    max_order = max_order_result if isinstance(max_order_result, (int, float)) else None
    next_order = 0 if max_order is None else int(max_order) + 1
    card = CreditCard(**payload.model_dump(), display_order=next_order)
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


def update_credit_card(session: Session, card: CreditCard, payload: CreditCardUpdate) -> CreditCard:
    update_data = payload.model_dump(exclude_unset=True)
    if "is_cancelled" in update_data:
        requested_cancelled = bool(update_data["is_cancelled"])
        if requested_cancelled and not card.is_cancelled:
            update_data.setdefault("cancelled_at", datetime.utcnow())
        elif not requested_cancelled and card.is_cancelled:
            update_data.setdefault("cancelled_at", None)
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
    statement = select(CreditCard).order_by(
        CreditCard.display_order, CreditCard.created_at, CreditCard.id
    )
    return session.exec(statement).all()


def reorder_credit_cards(session: Session, ordered_ids: Sequence[int]) -> List[CreditCard]:
    unique_ids = []
    seen: set[int] = set()
    for card_id in ordered_ids:
        if card_id in seen:
            raise ValueError("Card order cannot contain duplicates.")
        seen.add(card_id)
        unique_ids.append(card_id)

    if not unique_ids:
        return list_credit_cards(session)

    total_result = session.exec(select(func.count(CreditCard.id))).one()
    if isinstance(total_result, tuple):
        total_result = total_result[0]
    total_cards = int(total_result or 0)
    if total_cards != len(unique_ids):
        raise ValueError("Card order must include every card.")

    cards = session.exec(
        select(CreditCard).where(CreditCard.id.in_(unique_ids))
    ).all()
    if len(cards) != len(unique_ids):
        raise ValueError("One or more cards could not be found.")

    card_map = {card.id: card for card in cards if card.id is not None}
    for position, card_id in enumerate(unique_ids):
        card = card_map.get(card_id)
        if card is None:
            raise ValueError("One or more cards could not be found.")
        card.display_order = position
        session.add(card)

    session.commit()

    for card in card_map.values():
        session.refresh(card)

    return list_credit_cards(session)


def get_credit_card(session: Session, card_id: int) -> Optional[CreditCard]:
    return session.get(CreditCard, card_id)


def create_benefit(session: Session, card: CreditCard, payload: BenefitCreate) -> Benefit:
    data = payload.model_dump()
    value = data.pop("value", None)
    window_values = data.pop("window_values", None)
    benefit = Benefit(
        **data,
        credit_card_id=card.id,
        value=value if value is not None else 0,
        window_values=window_values,
    )
    if benefit.type == BenefitType.cumulative:
        benefit.window_tracking_mode = None
    session.add(benefit)
    session.commit()
    session.refresh(benefit)
    sync_benefit_usage_status(session, benefit)
    return benefit


def update_benefit(session: Session, benefit: Benefit, payload: BenefitUpdate) -> Benefit:
    update_data = payload.model_dump(exclude_unset=True)
    value = update_data.pop("value", None)
    is_used = update_data.pop("is_used", None)
    expected_value = update_data.pop("expected_value", None)
    raw_window_values = update_data.pop("window_values", None)
    new_type = update_data.get("type")
    new_frequency = update_data.get("frequency")

    if new_type and new_type != benefit.type:
        benefit.is_used = False
        benefit.used_at = None
        if new_type != BenefitType.cumulative:
            benefit.expected_value = None
        else:
            benefit.window_tracking_mode = None

    for key, item in update_data.items():
        setattr(benefit, key, item)

    if value is not None:
        benefit.value = value

    if "expected_value" in payload.model_fields_set:
        benefit.expected_value = expected_value

    target_frequency = new_frequency or benefit.frequency
    if "window_values" in payload.model_fields_set:
        if raw_window_values is None:
            benefit.window_values = None
        else:
            benefit.window_values = normalise_window_values(
                target_frequency, raw_window_values
            )

    if (
        new_frequency
        and new_frequency
        not in (
            BenefitFrequency.monthly,
            BenefitFrequency.quarterly,
            BenefitFrequency.semiannual,
            BenefitFrequency.yearly,
        )
    ):
        benefit.window_values = None
        benefit.window_tracking_mode = None

    if is_used is not None:
        if benefit.type == BenefitType.standard:
            benefit.is_used = is_used
            benefit.used_at = datetime.utcnow() if is_used else None
        elif benefit.type == BenefitType.cumulative:
            benefit.is_used = is_used
            benefit.used_at = datetime.utcnow() if is_used else None

    session.add(benefit)
    session.commit()
    session.refresh(benefit)
    sync_benefit_usage_status(session, benefit)
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


def list_benefit_window_exclusions(
    session: Session, benefit_ids: Sequence[int]
) -> Dict[int, List[BenefitWindowExclusion]]:
    if not benefit_ids:
        return {}
    statement = (
        select(BenefitWindowExclusion)
        .where(BenefitWindowExclusion.benefit_id.in_(benefit_ids))
        .order_by(BenefitWindowExclusion.window_start)
    )
    exclusions = session.exec(statement).all()
    grouped: Dict[int, List[BenefitWindowExclusion]] = {}
    for exclusion in exclusions:
        grouped.setdefault(exclusion.benefit_id, []).append(exclusion)
    return grouped


def get_benefit_window_exclusion(
    session: Session, exclusion_id: int
) -> BenefitWindowExclusion | None:
    return session.get(BenefitWindowExclusion, exclusion_id)


def create_benefit_window_exclusion(
    session: Session, benefit: Benefit, payload: BenefitWindowExclusionCreate
) -> BenefitWindowExclusion:
    data = payload.model_dump()
    exclusion = BenefitWindowExclusion(
        **data,
        benefit_id=benefit.id,
    )
    statement = select(BenefitWindowExclusion).where(
        BenefitWindowExclusion.benefit_id == benefit.id,
        BenefitWindowExclusion.window_start == exclusion.window_start,
        BenefitWindowExclusion.window_end == exclusion.window_end,
    )
    existing = session.exec(statement).first()
    if existing:
        return existing
    session.add(exclusion)
    session.commit()
    session.refresh(exclusion)
    return exclusion


def list_bugs(session: Session, *, completed: Optional[bool] = None) -> List[Bug]:
    statement = select(Bug)
    if completed is not None:
        statement = statement.where(Bug.is_completed == completed)
    statement = statement.order_by(Bug.created_at.desc())
    return session.exec(statement).all()


def get_bug(session: Session, bug_id: int) -> Optional[Bug]:
    return session.get(Bug, bug_id)


def create_bug(session: Session, payload: BugCreate) -> Bug:
    bug = Bug(description=payload.description)
    session.add(bug)
    session.commit()
    session.refresh(bug)
    return bug


def update_bug(session: Session, bug: Bug, payload: BugUpdate) -> Bug:
    update_data = payload.model_dump(exclude_unset=True)
    description = update_data.get("description")
    is_completed = update_data.get("is_completed")

    if description is not None:
        bug.description = description

    if is_completed is not None:
        bug.is_completed = is_completed
        if is_completed and bug.completed_at is None:
            bug.completed_at = datetime.utcnow()
        elif not is_completed:
            bug.completed_at = None

    session.add(bug)
    session.commit()
    session.refresh(bug)
    return bug


def delete_bug(session: Session, bug: Bug) -> None:
    session.delete(bug)
    session.commit()


def get_interface_settings(session: Session) -> InterfaceSettings:
    settings = session.get(InterfaceSettings, 1)
    if settings is None:
        settings = InterfaceSettings(id=1)
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


def update_interface_settings(
    session: Session, payload: InterfaceSettingsUpdate
) -> InterfaceSettings:
    settings = get_interface_settings(session)
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings, key, value)
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings


def delete_benefit_window_exclusion(
    session: Session, exclusion: BenefitWindowExclusion
) -> None:
    session.delete(exclusion)
    session.commit()


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
    sync_benefit_usage_status(session, benefit)
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
    sync_benefit_usage_status(session, redemption.benefit_id)
    return redemption


def delete_benefit_redemption(session: Session, redemption: BenefitRedemption) -> None:
    benefit_id = redemption.benefit_id
    session.delete(redemption)
    session.commit()
    sync_benefit_usage_status(session, benefit_id)


def get_notification_settings(session: Session) -> NotificationSettings | None:
    statement = select(NotificationSettings).limit(1)
    return session.exec(statement).first()


def upsert_notification_settings(
    session: Session, payload: NotificationSettingsWrite | NotificationSettingsUpdate
) -> NotificationSettings:
    data = payload.model_dump(exclude_unset=True)
    settings = get_notification_settings(session)
    now = datetime.utcnow()
    if settings is None:
        if not isinstance(payload, NotificationSettingsWrite):
            missing = {key for key in ("base_url", "webhook_id") if key not in data}
            if missing:
                raise ValueError(
                    "Missing required fields to create notification settings: "
                    + ", ".join(sorted(missing))
                )
        settings = NotificationSettings(**data)
        settings.created_at = now
    else:
        for key, value in data.items():
            setattr(settings, key, value)
    settings.updated_at = now
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings


def get_backup_settings(session: Session) -> BackupSettings | None:
    statement = select(BackupSettings).limit(1)
    return session.exec(statement).first()


def upsert_backup_settings(
    session: Session, payload: BackupSettingsWrite | BackupSettingsUpdate
) -> BackupSettings:
    data = payload.model_dump(exclude_unset=True)
    settings = get_backup_settings(session)
    now = datetime.utcnow()
    if settings is None:
        if not isinstance(payload, BackupSettingsWrite):
            raise ValueError("Backup settings have not been configured yet.")
        settings = BackupSettings(**data, created_at=now, updated_at=now)
        session.add(settings)
    else:
        for key, value in data.items():
            setattr(settings, key, value)
        settings.updated_at = now
        session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings


def record_backup_success(
    session: Session, settings: BackupSettings, *, timestamp: datetime, filename: str
) -> BackupSettings:
    settings.last_backup_at = timestamp
    settings.last_backup_filename = filename
    settings.last_backup_error = None
    settings.updated_at = datetime.utcnow()
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings


def record_backup_failure(
    session: Session, settings: BackupSettings, error_message: str
) -> BackupSettings:
    settings.last_backup_error = error_message
    settings.updated_at = datetime.utcnow()
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings


def log_notification_event(
    session: Session,
    *,
    event_type: str,
    title: str | None,
    body: str | None,
    target: str | None,
    sent: bool,
    response_message: str | None,
    categories: Dict[str, object] | None,
    reason: str | None,
) -> NotificationLog:
    entry = NotificationLog(
        event_type=event_type,
        title=title,
        body=body,
        target=target,
        sent=sent,
        response_message=response_message,
        reason=reason,
        categories=categories or {},
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def list_notification_logs(
    session: Session,
    *,
    limit: int = 50,
    search: Optional[str] = None,
    sort_direction: str = "desc",
) -> List[NotificationLog]:
    safe_limit = max(1, min(200, int(limit)))
    statement = select(NotificationLog)
    if search:
        term = str(search).strip()
        if term:
            pattern = f"%{term}%"
            statement = statement.where(
                or_(
                    NotificationLog.event_type.ilike(pattern),
                    NotificationLog.title.ilike(pattern),
                    NotificationLog.body.ilike(pattern),
                    NotificationLog.target.ilike(pattern),
                    NotificationLog.response_message.ilike(pattern),
                    NotificationLog.reason.ilike(pattern),
                )
            )
    direction = str(sort_direction or "desc").lower()
    if direction == "asc":
        statement = statement.order_by(
            NotificationLog.created_at.asc(), NotificationLog.id.asc()
        )
    else:
        statement = statement.order_by(
            NotificationLog.created_at.desc(), NotificationLog.id.desc()
        )
    statement = statement.limit(safe_limit)
    return session.exec(statement).all()


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


def _safe_day(year: int, month: int, day: int) -> int:
    _, last_day = calendar.monthrange(year, month)
    return min(day, last_day)


def _compute_cycle_bounds(card: CreditCard, mode: YearTrackingMode, reference: date) -> tuple[date, date]:
    if mode == YearTrackingMode.anniversary:
        due_month = card.fee_due_date.month
        due_day = card.fee_due_date.day
        cycle_end = date(reference.year, due_month, _safe_day(reference.year, due_month, due_day))
        if cycle_end <= reference:
            cycle_end = date(
                reference.year + 1,
                due_month,
                _safe_day(reference.year + 1, due_month, due_day),
            )
        cycle_start = date(
            cycle_end.year - 1,
            due_month,
            _safe_day(cycle_end.year - 1, due_month, due_day),
        )
    else:
        cycle_start = date(reference.year, 1, 1)
        cycle_end = date(reference.year + 1, 1, 1)
    return cycle_start, cycle_end


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = _safe_day(year, month, value.day)
    return date(year, month, day)


def _resolve_window_bounds(
    session: Session, card: CreditCard, benefit: Benefit, reference: date
) -> tuple[date, date, int]:
    mode = benefit.window_tracking_mode or card.year_tracking_mode
    cycle_start, cycle_end = _compute_cycle_bounds(card, mode, reference)
    if benefit.frequency == BenefitFrequency.yearly:
        return cycle_start, cycle_end, 1

    months_map = {
        BenefitFrequency.monthly: 1,
        BenefitFrequency.quarterly: 3,
        BenefitFrequency.semiannual: 6,
    }
    months = months_map.get(benefit.frequency)
    if not months:
        return cycle_start, cycle_end, 1

    cursor = cycle_start
    index = 1
    windows: List[tuple[date, date, int]] = []
    while cursor < cycle_end:
        window_end = _add_months(cursor, months)
        if window_end > cycle_end:
            window_end = cycle_end
        windows.append((cursor, window_end, index))
        cursor = window_end
        index += 1

    exclusions = list_benefit_window_exclusions(session, [benefit.id]).get(benefit.id, [])
    active_windows: List[tuple[date, date, int]] = []
    for window_start, window_end, window_index in windows:
        if any(
            _window_matches_exclusion(window_start, window_end, window_index, exclusion)
            for exclusion in exclusions
        ):
            continue
        active_windows.append((window_start, window_end, window_index))

    if not active_windows:
        return cycle_start, cycle_end, 1

    for window_start, window_end, window_index in active_windows:
        if window_start <= reference < window_end:
            return window_start, window_end, window_index

    return active_windows[-1]


def _window_matches_exclusion(
    window_start: date,
    window_end: date,
    window_index: int,
    exclusion: BenefitWindowExclusion,
) -> bool:
    if exclusion.window_index and exclusion.window_index == window_index:
        return True
    if exclusion.window_start == window_start and exclusion.window_end == window_end:
        return True
    return False


def _resolve_window_target(benefit: Benefit, window_index: int) -> float:
    if window_index <= 0:
        window_index = 1
    window_values = benefit.window_values or []
    idx = window_index - 1
    if 0 <= idx < len(window_values) and window_values[idx] is not None:
        return float(window_values[idx])
    if benefit.value is not None:
        return float(benefit.value)
    return 0.0


def sync_benefit_usage_status(session: Session, benefit: Benefit | int) -> None:
    if isinstance(benefit, int):
        benefit_obj = session.get(Benefit, benefit)
    else:
        benefit_obj = benefit
    if not benefit_obj or benefit_obj.id is None:
        return

    if benefit_obj.type not in (BenefitType.incremental, BenefitType.standard):
        return

    card = session.get(CreditCard, benefit_obj.credit_card_id)
    if not card:
        return

    today = date.today()
    window_start, window_end, window_index = _resolve_window_bounds(
        session, card, benefit_obj, today
    )
    if window_start >= window_end:
        totals = {}
    else:
        totals = redemption_summary_for_benefits(
            session, [benefit_obj.id], window_start, window_end
        )
    total_amount, count = totals.get(benefit_obj.id, (0.0, 0))

    if benefit_obj.type == BenefitType.incremental:
        target_value = _resolve_window_target(benefit_obj, window_index)
        should_be_used = target_value > 0 and total_amount >= target_value
    else:
        should_be_used = count > 0

    if benefit_obj.is_used != should_be_used:
        benefit_obj.is_used = should_be_used
        benefit_obj.used_at = datetime.utcnow() if should_be_used else None
        session.add(benefit_obj)
        session.commit()
        session.refresh(benefit_obj)
