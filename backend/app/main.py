from __future__ import annotations

import calendar
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from . import crud
from .backups import BackupService
from .database import DATABASE_PATH, engine, get_session, init_db
from .models import (
    BackupSettings,
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
    BackupSettingsRead,
    BackupSettingsUpdate,
    BackupSettingsWrite,
    NotificationCustomMessage,
    NotificationDailyTestRequest,
    NotificationDispatchResult,
    NotificationSettingsRead,
    NotificationSettingsUpdate,
    NotificationSettingsWrite,
    PreconfiguredCardRead,
    PreconfiguredCardWrite,
)
from .preconfigured import (
    create_preconfigured_card,
    delete_preconfigured_card,
    load_preconfigured_cards,
    update_preconfigured_card,
)
from .notifications import NotificationService

app = FastAPI(title="CreditWatch", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


DATABASE_FILE = Path(DATABASE_PATH) / "creditwatch.db"


def _get_backup_service(optional: bool = False) -> BackupService | None:
    service: BackupService | None = getattr(app.state, "backup_service", None)
    if service is None and not optional:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backup service is not ready.",
        )
    return service


def schedule_backup_after_change() -> None:
    service = _get_backup_service(optional=True)
    if service is not None:
        service.notify_change()


def build_backup_settings_response(settings: BackupSettings | None) -> BackupSettingsRead:
    service = _get_backup_service(optional=True)
    status_info = service.get_status() if service is not None else {}
    last_result = status_info.get("last_result") if status_info else None
    payload = {
        "drive_folder_id": settings.drive_folder_id if settings else None,
        "service_account_email": settings.service_account_email if settings else None,
        "is_configured": bool(settings.is_configured) if settings else False,
        "last_backup_at": settings.last_backup_at if settings else None,
        "last_backup_filename": settings.last_backup_filename if settings else None,
        "last_backup_size": settings.last_backup_size if settings else None,
        "last_backup_error": settings.last_backup_error if settings else None,
        "next_backup_at": status_info.get("next_run_at"),
        "last_result_at": last_result.timestamp if last_result else None,
        "last_result_message": last_result.message if last_result else None,
        "last_result_success": last_result.success if last_result else None,
    }
    return BackupSettingsRead(**payload)


def require_backup_service() -> BackupService:
    service = _get_backup_service(optional=False)
    assert service is not None
    return service


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    notification_service = NotificationService(engine=engine)
    notification_service.start()
    app.state.notification_service = notification_service
    backup_service = BackupService(engine=engine)
    backup_service.start()
    backup_service.refresh_configuration()
    app.state.backup_service = backup_service


@app.on_event("shutdown")
async def on_shutdown() -> None:
    backup_service: BackupService | None = getattr(app.state, "backup_service", None)
    if backup_service is not None:
        await backup_service.stop()
    service: NotificationService | None = getattr(app.state, "notification_service", None)
    if service is not None:
        await service.stop()


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


def get_notification_service() -> NotificationService:
    service: NotificationService | None = getattr(app.state, "notification_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Notification service is not ready.",
        )
    return service


@app.get(
    "/api/admin/notifications/settings",
    response_model=Optional[NotificationSettingsRead],
)
def get_notification_settings(session: Session = Depends(get_session)) -> NotificationSettingsRead | None:
    settings = crud.get_notification_settings(session)
    return NotificationSettingsRead.model_validate(settings, from_attributes=True) if settings else None


@app.put(
    "/api/admin/notifications/settings",
    response_model=NotificationSettingsRead,
)
def put_notification_settings(
    payload: NotificationSettingsWrite, session: Session = Depends(get_session)
) -> NotificationSettingsRead:
    settings = crud.upsert_notification_settings(session, payload)
    schedule_backup_after_change()
    return NotificationSettingsRead.model_validate(settings, from_attributes=True)


@app.patch(
    "/api/admin/notifications/settings",
    response_model=NotificationSettingsRead,
)
def patch_notification_settings(
    payload: NotificationSettingsUpdate, session: Session = Depends(get_session)
) -> NotificationSettingsRead:
    try:
        settings = crud.upsert_notification_settings(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    schedule_backup_after_change()
    return NotificationSettingsRead.model_validate(settings, from_attributes=True)


@app.get(
    "/api/admin/backups/settings",
    response_model=BackupSettingsRead,
)
def get_backup_settings_endpoint(
    session: Session = Depends(get_session),
) -> BackupSettingsRead:
    settings = crud.get_backup_settings(session)
    return build_backup_settings_response(settings)


@app.put(
    "/api/admin/backups/settings",
    response_model=BackupSettingsRead,
)
def put_backup_settings(
    payload: BackupSettingsWrite, session: Session = Depends(get_session)
) -> BackupSettingsRead:
    try:
        settings = crud.upsert_backup_settings(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    service = _get_backup_service(optional=True)
    if service is not None:
        service.apply_settings_change(settings.is_configured)
    return build_backup_settings_response(settings)


@app.patch(
    "/api/admin/backups/settings",
    response_model=BackupSettingsRead,
)
def patch_backup_settings(
    payload: BackupSettingsUpdate, session: Session = Depends(get_session)
) -> BackupSettingsRead:
    try:
        settings = crud.upsert_backup_settings(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    service = _get_backup_service(optional=True)
    if service is not None:
        service.apply_settings_change(settings.is_configured)
    return build_backup_settings_response(settings)


@app.post("/api/admin/backups/run")
async def run_backup_now(
    service: BackupService = Depends(require_backup_service),
) -> Dict[str, object]:
    result = await service.run_immediately()
    response: Dict[str, object] = {
        "success": result.success,
        "message": result.message,
        "timestamp": result.timestamp,
    }
    if result.file_name:
        response["file_name"] = result.file_name
    if result.file_id:
        response["file_id"] = result.file_id
    if result.size_bytes is not None:
        response["size_bytes"] = result.size_bytes
    return response


@app.post("/api/admin/backups/import")
async def import_database(file: UploadFile = File(...)) -> Dict[str, str]:
    filename = (file.filename or "").lower()
    if not filename.endswith(".db"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload a valid SQLite .db file.",
        )
    temp_path = Path(DATABASE_PATH) / f"import-{uuid4().hex}.db"
    try:
        with temp_path.open("wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                buffer.write(chunk)
    finally:
        await file.close()

    if not temp_path.exists() or temp_path.stat().st_size == 0:
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded database file is empty.",
        )

    target_path = DATABASE_FILE
    backup_path = target_path.with_suffix(".bak")

    try:
        if target_path.exists():
            if backup_path.exists():
                backup_path.unlink()
            target_path.replace(backup_path)
        shutil.move(temp_path, target_path)
        engine.dispose()
        init_db()
    except Exception as exc:  # pragma: no cover - defensive guard
        if temp_path.exists():
            temp_path.unlink()
        if target_path.exists():
            target_path.unlink()
        if backup_path.exists():
            backup_path.replace(target_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to import database.",
        ) from exc

    if backup_path.exists():
        backup_path.unlink()
    schedule_backup_after_change()
    return {"status": "imported"}


@app.post(
    "/api/admin/notifications/test/custom",
    response_model=NotificationDispatchResult,
)
async def trigger_custom_notification(
    payload: NotificationCustomMessage,
    service: NotificationService = Depends(get_notification_service),
) -> NotificationDispatchResult:
    return await service.send_custom_message(
        payload.message,
        title=payload.title,
        target_override=payload.target_override,
    )


@app.post(
    "/api/admin/notifications/test/daily",
    response_model=NotificationDispatchResult,
)
async def trigger_daily_notification_test(
    payload: NotificationDailyTestRequest,
    service: NotificationService = Depends(get_notification_service),
) -> NotificationDispatchResult:
    return await service.send_daily_notifications(
        payload.target_date,
        target_override=payload.target_override,
    )


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
    schedule_backup_after_change()
    return build_card_response(session, card)


@app.put("/api/cards/{card_id}", response_model=CreditCardWithBenefits)
def update_card(
    card_id: int, payload: CreditCardUpdate, session: Session = Depends(get_session)
) -> CreditCardWithBenefits:
    card = require_card(session, card_id)
    updated = crud.update_credit_card(session, card, payload)
    schedule_backup_after_change()
    return build_card_response(session, updated)


@app.delete(
    "/api/cards/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_card(card_id: int, session: Session = Depends(get_session)) -> Response:
    card = require_card(session, card_id)
    crud.delete_credit_card(session, card)
    schedule_backup_after_change()
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
    schedule_backup_after_change()
    return build_enriched_benefit(session, benefit, card)


@app.put("/api/benefits/{benefit_id}", response_model=BenefitRead)
def update_benefit(
    benefit_id: int, payload: BenefitUpdate, session: Session = Depends(get_session)
) -> BenefitRead:
    benefit = require_benefit(session, benefit_id)
    try:
        updated = crud.update_benefit(session, benefit, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    schedule_backup_after_change()
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
    schedule_backup_after_change()
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
    schedule_backup_after_change()
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
    schedule_backup_after_change()
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
    schedule_backup_after_change()
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
    schedule_backup_after_change()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def build_card_response(session: Session, card: CreditCard) -> CreditCardWithBenefits:
    raw_benefits = crud.list_benefits_for_card(session, card.id)
    metrics = gather_benefit_metrics(session, card, raw_benefits)
    overall_totals = metrics["overall"]
    cycle_totals = metrics["cycle"]
    window_totals = metrics["window_totals"]
    window_info = metrics["window_info"]
    cycle_label = metrics["cycle_label"]
    cycle_end = metrics["cycle_end"]

    benefits: List[BenefitRead] = []
    for benefit in raw_benefits:
        frequency = benefit.frequency
        summary = overall_totals.get(benefit.id)
        cycle_total = cycle_totals.get(benefit.id, (0.0, 0))[0]
        info = window_info.get(frequency, {})
        window_label = info.get("label") or cycle_label
        frequency_totals = window_totals.get(frequency, {})
        window_entry = frequency_totals.get(benefit.id)
        window_index = info.get("index") if isinstance(info.get("index"), int) else None
        window_count = info.get("count") if isinstance(info.get("count"), int) else None
        if frequency == BenefitFrequency.yearly:
            current_window_total = cycle_total
        else:
            current_window_total = window_entry[0] if window_entry else 0.0
        expiration = _compute_benefit_expiration(benefit, cycle_end, window_info)
        current_window_value = _resolve_current_window_value(benefit, window_index)
        cycle_target_value = _calculate_cycle_target_value(benefit, window_count)
        benefits.append(
            build_benefit_read(
                benefit,
                summary,
                cycle_total,
                cycle_label,
                current_window_total,
                window_label,
                expiration,
                current_window_value,
                window_index,
                window_count,
                cycle_target_value,
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
        year_tracking_mode=card.year_tracking_mode,
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


def _format_frequency_label(
    frequency: BenefitFrequency,
    index: int,
    window_start: date,
    window_end: date,
    is_calendar_year: bool,
) -> str:
    inclusive_end = window_end - timedelta(days=1)
    if frequency == BenefitFrequency.monthly:
        if is_calendar_year:
            return window_start.strftime("%b")
        return f"({window_start.strftime('%b %d')} - {inclusive_end.strftime('%b %d')})"
    if frequency == BenefitFrequency.quarterly:
        prefix = f"Q{index}"
        if is_calendar_year:
            return f"({prefix}: {window_start.strftime('%b')} - {inclusive_end.strftime('%b')})"
        return f"({prefix}: {window_start.strftime('%b %d')} - {inclusive_end.strftime('%b %d')})"
    if frequency == BenefitFrequency.semiannual:
        prefix = f"H{index}"
        if is_calendar_year:
            return f"({prefix}: {window_start.strftime('%b')} - {inclusive_end.strftime('%b')})"
        return f"({prefix}: {window_start.strftime('%b %d')} - {inclusive_end.strftime('%b %d')})"
    if frequency == BenefitFrequency.yearly:
        if is_calendar_year:
            return str(window_start.year)
        return f"({window_start.strftime('%m/%d/%Y')} - {inclusive_end.strftime('%m/%d/%Y')})"
    return _format_range_label(window_start, window_end)


def _current_frequency_window(
    cycle_start: date,
    cycle_end: date,
    frequency: BenefitFrequency,
    reference: date | None = None,
    *,
    is_calendar_year: bool = False,
) -> Tuple[date, date, str, int, int]:
    reference_date = reference or date.today()
    months_map = {
        BenefitFrequency.monthly: 1,
        BenefitFrequency.quarterly: 3,
        BenefitFrequency.semiannual: 6,
        BenefitFrequency.yearly: 12,
    }
    months = months_map.get(frequency)
    if not months:
        label = _format_range_label(cycle_start, cycle_end)
        return cycle_start, cycle_end, label, 1, 1
    windows: List[Tuple[date, date, str, int]] = []
    index = 1
    cursor = cycle_start
    while cursor < cycle_end:
        window_end = _add_months(cursor, months)
        if window_end > cycle_end:
            window_end = cycle_end
        label = _format_frequency_label(
            frequency, index, cursor, window_end, is_calendar_year
        )
        windows.append((cursor, window_end, label, index))
        cursor = window_end
        index += 1
    if not windows:
        label = _format_frequency_label(
            frequency, 1, cycle_start, cycle_end, is_calendar_year
        )
        return cycle_start, cycle_end, label, 1, 1
    for window_start, window_end, label, idx in windows:
        if window_start <= reference_date < window_end:
            return window_start, window_end, label, idx, len(windows)
    last_start, last_end, last_label, last_idx = windows[-1]
    return last_start, last_end, last_label, last_idx, len(windows)


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
    is_calendar_year = card.year_tracking_mode == YearTrackingMode.calendar
    for frequency in BenefitFrequency:
        window_start, window_end, label, index, total_windows = _current_frequency_window(
            cycle_start,
            cycle_end,
            frequency,
            is_calendar_year=is_calendar_year,
        )
        window_info[frequency] = {
            "start": window_start,
            "end": window_end,
            "label": label,
            "index": index,
            "count": total_windows,
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
        "cycle_start": cycle_start,
        "cycle_end": cycle_end,
    }


def _compute_benefit_expiration(
    benefit: Benefit,
    cycle_end: date,
    window_info: Dict[BenefitFrequency, Dict[str, object]],
) -> date | None:
    if benefit.expiration_date:
        return benefit.expiration_date
    frequency = benefit.frequency
    if frequency == BenefitFrequency.yearly:
        return cycle_end - timedelta(days=1)
    if frequency in (
        BenefitFrequency.monthly,
        BenefitFrequency.quarterly,
        BenefitFrequency.semiannual,
    ):
        info = window_info.get(frequency) or {}
        window_end = info.get("end")
        if isinstance(window_end, date):
            return window_end - timedelta(days=1)
    return None


def _resolve_current_window_value(
    benefit: Benefit, window_index: Optional[int]
) -> Optional[float]:
    if benefit.type == BenefitType.cumulative:
        return None
    if window_index is not None and benefit.window_values:
        idx = window_index - 1
        if 0 <= idx < len(benefit.window_values):
            return float(benefit.window_values[idx])
    if benefit.value is None:
        return None
    return float(benefit.value)


def _calculate_cycle_target_value(
    benefit: Benefit | BenefitRead, window_count: Optional[int]
) -> Optional[float]:
    if benefit.type == BenefitType.cumulative:
        expected = getattr(benefit, "expected_value", None)
        if expected is None:
            return None
        return float(expected)

    base_value = getattr(benefit, "value", None)
    windows = getattr(benefit, "window_values", None) or []
    if not window_count or window_count <= 0:
        return float(base_value) if base_value is not None else None

    total = 0.0
    for idx in range(window_count):
        if idx < len(windows):
            total += float(windows[idx] or 0)
        elif base_value is not None:
            total += float(base_value)
    if total == 0.0 and base_value is None and not windows:
        return None
    if total == 0.0 and base_value is not None and not windows:
        return float(base_value) * window_count
    return total


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
    window_index = info.get("index") if isinstance(info.get("index"), int) else None
    window_count = info.get("count") if isinstance(info.get("count"), int) else None
    if frequency == BenefitFrequency.yearly:
        current_window_total = cycle_total
    else:
        current_window_total = window_entry[0] if window_entry else 0.0
    expiration = _compute_benefit_expiration(
        benefit, metrics["cycle_end"], metrics["window_info"]
    )
    current_window_value = _resolve_current_window_value(benefit, window_index)
    cycle_target_value = _calculate_cycle_target_value(benefit, window_count)
    return build_benefit_read(
        benefit,
        summary,
        cycle_total,
        metrics["cycle_label"],
        current_window_total,
        window_label,
        expiration,
        current_window_value,
        window_index,
        window_count,
        cycle_target_value,
    )


def build_benefit_read(
    benefit: Benefit,
    redemption_summary: Tuple[float, int] | None,
    cycle_total: float,
    cycle_label: str,
    window_total: float | None,
    window_label: Optional[str],
    expiration_date: date | None,
    current_window_value: Optional[float],
    window_index: Optional[int],
    window_count: Optional[int],
    cycle_target_value: Optional[float],
) -> BenefitRead:
    total, count = redemption_summary or (0.0, 0)
    cycle_value = float(cycle_total)
    window_value = float(window_total) if window_total is not None else None
    remaining: Optional[float]
    if benefit.type == BenefitType.incremental:
        target = float(cycle_target_value or 0)
        remaining = max(target - cycle_value, 0)
    else:
        remaining = None
    cycle_target = (
        float(cycle_target_value)
        if cycle_target_value is not None
        else (float(benefit.expected_value) if benefit.expected_value is not None else None)
    )
    return BenefitRead(
        id=benefit.id,
        credit_card_id=benefit.credit_card_id,
        name=benefit.name,
        description=benefit.description,
        frequency=benefit.frequency,
        type=benefit.type,
        value=benefit.value,
        expected_value=benefit.expected_value,
        window_values=list(benefit.window_values or []),
        expiration_date=expiration_date,
        is_used=benefit.is_used,
        used_at=benefit.used_at,
        redemption_total=total,
        redemption_count=count,
        remaining_value=remaining,
        cycle_redemption_total=cycle_value,
        cycle_label=cycle_label,
        current_window_total=window_value,
        current_window_label=window_label,
        current_window_value=current_window_value,
        current_window_index=window_index,
        cycle_window_count=window_count,
        cycle_target_value=cycle_target,
    )


def compute_benefit_totals(benefit: BenefitRead) -> Tuple[float, float]:
    cycle_total = float(benefit.cycle_redemption_total or 0)
    target_value = (
        float(benefit.cycle_target_value)
        if benefit.cycle_target_value is not None
        else None
    )
    if benefit.type == BenefitType.standard:
        potential = target_value if target_value is not None else float(benefit.value or 0)
        utilized = potential if benefit.is_used else 0.0
    elif benefit.type == BenefitType.incremental:
        potential = target_value if target_value is not None else float(benefit.value or 0)
        utilized = min(cycle_total, potential)
    else:
        if benefit.expected_value is not None:
            potential = float(benefit.expected_value)
            utilized = min(cycle_total, potential)
        else:
            potential = cycle_total
            utilized = cycle_total
    return potential, utilized
