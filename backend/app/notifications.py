from __future__ import annotations

import asyncio
import calendar
import logging
from contextlib import suppress
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple

import httpx
from sqlmodel import Session, select

from . import crud
from .models import (
    Benefit,
    BenefitFrequency,
    BenefitType,
    CreditCard,
    NotificationSettings,
    YearTrackingMode,
)
from .schemas import (
    NotificationBenefitSummary,
    NotificationCancelledCardSummary,
    NotificationDispatchResult,
)


NotificationCategoryMap = Dict[
    str, List[NotificationBenefitSummary | NotificationCancelledCardSummary]
]

logger = logging.getLogger("creditwatch.notifications")


def _safe_day(year: int, month: int, day: int) -> int:
    _, last_day = calendar.monthrange(year, month)
    return min(day, last_day)


def _compute_cycle_bounds(
    card: CreditCard, mode: YearTrackingMode, reference: date
) -> Tuple[date, date]:
    if mode == YearTrackingMode.anniversary:
        due_month = card.fee_due_date.month
        due_day = card.fee_due_date.day
        cycle_end = date(
            reference.year, due_month, _safe_day(reference.year, due_month, due_day)
        )
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


def _resolve_next_fee_due_date(card: CreditCard, reference: date) -> Optional[date]:
    due_date = card.fee_due_date
    if not isinstance(due_date, date):
        return None
    due_month = due_date.month
    due_day = due_date.day
    candidate = date(reference.year, due_month, _safe_day(reference.year, due_month, due_day))
    if candidate <= reference:
        candidate = date(
            reference.year + 1,
            due_month,
            _safe_day(reference.year + 1, due_month, due_day),
        )
    return candidate


def _enumerate_frequency_windows(
    cycle_start: date, cycle_end: date, frequency: BenefitFrequency
) -> List[Tuple[date, date]]:
    months_map = {
        BenefitFrequency.monthly: 1,
        BenefitFrequency.quarterly: 3,
        BenefitFrequency.semiannual: 6,
        BenefitFrequency.yearly: 12,
    }
    months = months_map.get(frequency)
    if not months:
        return []
    windows: List[Tuple[date, date]] = []
    cursor = cycle_start
    while cursor < cycle_end:
        window_end = _add_months(cursor, months)
        if window_end > cycle_end:
            window_end = cycle_end
        windows.append((cursor, window_end))
        cursor = window_end
    return windows


def _compute_override_expiration(
    card: CreditCard, benefit: Benefit, start: date, end: date
) -> Optional[date]:
    tracking_mode = benefit.window_tracking_mode or card.year_tracking_mode
    cycle_start, cycle_end = _compute_cycle_bounds(card, tracking_mode, end)

    if benefit.frequency == BenefitFrequency.yearly:
        candidate = cycle_end - timedelta(days=1)
        return candidate if start <= candidate <= end else None

    if benefit.frequency in (
        BenefitFrequency.monthly,
        BenefitFrequency.quarterly,
        BenefitFrequency.semiannual,
    ):
        for window_start, window_end in _enumerate_frequency_windows(
            cycle_start, cycle_end, benefit.frequency
        ):
            if window_start >= window_end:
                continue
            candidate = window_end - timedelta(days=1)
            if start <= candidate <= end:
                return candidate

    return None


class NotificationService:
    """Service responsible for orchestrating notification delivery."""

    def __init__(self, *, engine) -> None:
        self._engine = engine
        self._task: asyncio.Task[None] | None = None
        self._last_run_date: date | None = None

    def start(self) -> None:
        """Begin the background scheduler if it is not already running."""

        if self._task is None:
            self._task = asyncio.create_task(self._run_scheduler())

    async def stop(self) -> None:
        """Stop the background scheduler gracefully."""

        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def send_custom_message(
        self, message: str, *, title: Optional[str] = None, target_override: Optional[str] = None
    ) -> NotificationDispatchResult:
        """Send a free-form notification payload."""

        with Session(self._engine) as session:
            settings = crud.get_notification_settings(session)
        result = await self._send_payload(
            settings,
            title or "CreditWatch notification",
            message,
            {},
            target_override=target_override,
        )
        await asyncio.to_thread(
            self._record_history,
            "custom",
            title or "CreditWatch notification",
            message,
            result.target,
            result,
        )
        return result

    async def send_daily_notifications(
        self, target_date: Optional[date] = None, *, target_override: Optional[str] = None
    ) -> NotificationDispatchResult:
        """Compute and dispatch the daily reminder notification if required."""

        target = target_date or date.today()
        with Session(self._engine) as session:
            categories = self._collect_categories(session, target)
            settings = crud.get_notification_settings(session)
        title = f"CreditWatch reminders for {target.strftime('%B %d, %Y')}"
        body: Optional[str] = None
        if not categories:
            result = NotificationDispatchResult(
                sent=False,
                message="No expiring benefits to report.",
                categories={},
                target=target_override
                or (settings.default_target if settings else None),
            )
        else:
            body = self._render_daily_body(target, categories)
            result = await self._send_payload(
                settings,
                title,
                body,
                categories,
                target_override=target_override,
            )
        if target_date is None:
            self._last_run_date = target
        await asyncio.to_thread(
            self._record_history,
            "daily" if target_date is None else "daily_test",
            title,
            body,
            result.target,
            result,
        )
        return result

    async def _run_scheduler(self) -> None:
        """Background loop that triggers daily reminders at 8 AM."""

        while True:
            try:
                wait_seconds = self._seconds_until_next_run()
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)
                result = await self.send_daily_notifications()
                if result.sent:
                    logger.info("Daily notification dispatched")
                else:
                    logger.debug("Daily notification skipped: %s", result.message)
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover - defensive logging
                logger.exception("Unhandled error while running notification scheduler")
                await asyncio.sleep(60)

    def _seconds_until_next_run(self) -> float:
        now = datetime.now()
        today_run = datetime.combine(now.date(), time(hour=8, minute=0))
        if now < today_run and self._last_run_date != now.date():
            return max(0.0, (today_run - now).total_seconds())
        if self._last_run_date != now.date():
            # We have not yet executed today but it is after 8am; run immediately.
            return 0.0
        tomorrow_run = datetime.combine(now.date() + timedelta(days=1), time(hour=8, minute=0))
        return max(0.0, (tomorrow_run - now).total_seconds())

    def _collect_categories(
        self, session: Session, target: date
    ) -> NotificationCategoryMap:
        categories: NotificationCategoryMap = {}
        if target.day == 1:
            start_of_month = target.replace(day=1)
            end_of_month = date(
                target.year,
                target.month,
                calendar.monthrange(target.year, target.month)[1],
            )
            monthly = self._fetch_benefits(session, start_of_month, end_of_month)
            if monthly:
                categories["expiring_this_month"] = monthly
        ten_day = self._fetch_benefits(session, target + timedelta(days=10), target + timedelta(days=10))
        if ten_day:
            categories["expiring_in_10_days"] = ten_day
        today = self._fetch_benefits(session, target, target)
        if today:
            categories["expiring_today"] = today
        cancelled_cards = self._collect_cancelled_cards(session, target)
        if cancelled_cards:
            categories["cancelled_cards"] = cancelled_cards
        return categories

    def _fetch_benefits(
        self, session: Session, start: date, end: date
    ) -> List[NotificationBenefitSummary]:
        statement = (
            select(Benefit, CreditCard)
            .join(CreditCard, CreditCard.id == Benefit.credit_card_id)
            .where(Benefit.type != BenefitType.cumulative)
            .where(Benefit.exclude_from_notifications.is_(False))
            .where(
                Benefit.expiration_date.is_not(None)
                | Benefit.window_tracking_mode.is_not(None)
            )
            .order_by(Benefit.expiration_date, CreditCard.card_name, Benefit.name)
        )
        results: List[NotificationBenefitSummary] = []
        for benefit, card in session.exec(statement).all():
            expiration_raw = benefit.expiration_date
            expiration: Optional[date] = None
            if benefit.window_tracking_mode is not None:
                expiration = _compute_override_expiration(card, benefit, start, end)
                supported_frequencies = {
                    BenefitFrequency.monthly,
                    BenefitFrequency.quarterly,
                    BenefitFrequency.semiannual,
                    BenefitFrequency.yearly,
                }
                if (
                    expiration is None
                    and benefit.frequency not in supported_frequencies
                    and expiration_raw is not None
                    and start <= expiration_raw <= end
                ):
                    expiration = expiration_raw
            else:
                if expiration_raw is not None and start <= expiration_raw <= end:
                    expiration = expiration_raw

            if expiration is None:
                continue

            expiration = self._resolve_display_expiration(benefit, card, expiration)
            results.append(
                NotificationBenefitSummary(
                    card_name=card.card_name,
                    benefit_name=benefit.name,
                    expiration_date=expiration,
                )
            )
        return results

    def _collect_cancelled_cards(
        self, session: Session, target: date
    ) -> List[NotificationCancelledCardSummary]:
        statement = (
            select(CreditCard)
            .where(CreditCard.is_cancelled.is_(True))
            .order_by(CreditCard.fee_due_date, CreditCard.card_name)
        )
        summaries: List[NotificationCancelledCardSummary] = []
        for card in session.exec(statement).all():
            reference = (
                card.cancelled_at.date()
                if isinstance(card.cancelled_at, datetime)
                else target
            )
            due_date = _resolve_next_fee_due_date(card, reference)
            if due_date is None:
                continue
            if due_date < target:
                due_date = _resolve_next_fee_due_date(card, target)
                if due_date is None:
                    continue
            reminder_start = due_date - timedelta(days=15)
            if target < reminder_start:
                continue
            days_until_due = (due_date - target).days
            summaries.append(
                NotificationCancelledCardSummary(
                    card_name=card.card_name,
                    account_name=card.account_name,
                    company_name=card.company_name,
                    fee_due_date=due_date,
                    days_until_due=days_until_due,
                )
            )
        return summaries

    def _resolve_display_expiration(
        self, benefit: Benefit, card: CreditCard, expiration: date
    ) -> date:
        tracking_mode = benefit.window_tracking_mode or card.year_tracking_mode
        if tracking_mode == YearTrackingMode.calendar:
            last_day = calendar.monthrange(expiration.year, expiration.month)[1]
            if expiration.day != last_day:
                return expiration.replace(day=last_day)
        return expiration

    def _render_daily_body(self, target: date, categories: NotificationCategoryMap) -> str:
        sections: List[str] = []
        month_section = categories.get("expiring_this_month")
        if month_section:
            sections.append(
                "Benefits expiring this month:\n"
                + "\n".join(self._format_benefit_line(item) for item in month_section)
            )
        ten_day_section = categories.get("expiring_in_10_days")
        if ten_day_section:
            sections.append(
                "Benefits expiring in 10 days:\n"
                + "\n".join(self._format_benefit_line(item) for item in ten_day_section)
            )
        today_section = categories.get("expiring_today")
        if today_section:
            sections.append(
                "Benefits expiring today:\n"
                + "\n".join(self._format_benefit_line(item) for item in today_section)
            )
        cancelled_section = categories.get("cancelled_cards")
        if cancelled_section:
            sections.append(
                "Cards to be Canceled approaching annual fees:\n"
                + "\n".join(self._format_cancelled_line(item) for item in cancelled_section)
            )
        return "\n\n".join(sections)

    def _format_benefit_line(self, summary: NotificationBenefitSummary) -> str:
        return f"- {summary.benefit_name} ({summary.card_name}) – {summary.expiration_date:%b %d}" \
            if summary.expiration_date else f"- {summary.benefit_name} ({summary.card_name})"

    def _format_cancelled_line(self, summary: NotificationCancelledCardSummary) -> str:
        base = f"- {summary.card_name}"
        if summary.account_name:
            base += f" ({summary.account_name})"
        if summary.days_until_due > 0:
            timing = f"in {summary.days_until_due} day"
            if summary.days_until_due != 1:
                timing += "s"
            suffix = f"Annual fee due {summary.fee_due_date:%b %d} ({timing})"
        elif summary.days_until_due == 0:
            suffix = f"Annual fee due today ({summary.fee_due_date:%b %d})"
        else:
            overdue = abs(summary.days_until_due)
            timing = f"{overdue} day"
            if overdue != 1:
                timing += "s"
            suffix = f"Annual fee overdue by {timing} ({summary.fee_due_date:%b %d})"
        return f"{base} – {suffix}"

    async def _send_payload(
        self,
        settings: NotificationSettings | None,
        title: str,
        message: str,
        categories: NotificationCategoryMap,
        *,
        target_override: Optional[str] = None,
    ) -> NotificationDispatchResult:
        target_value = target_override
        if settings is None:
            return NotificationDispatchResult(
                sent=False,
                message="Notification settings have not been configured.",
                categories=categories,
                target=target_value,
            )
        target_value = target_override or settings.default_target
        if not settings.enabled:
            return NotificationDispatchResult(
                sent=False,
                message="Notifications are currently disabled.",
                categories=categories,
                target=target_value,
            )
        payload = {"title": title, "message": message}
        if target_value:
            payload["target"] = target_value
        url = f"{settings.base_url}/api/webhook/{settings.webhook_id}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.exception("Failed to deliver notification to Home Assistant")
            return NotificationDispatchResult(
                sent=False,
                message=f"Failed to deliver notification: {exc}",
                categories=categories,
                target=target_value,
            )
        return NotificationDispatchResult(
            sent=True,
            message="Notification delivered successfully.",
            categories=categories,
            target=target_value,
        )

    def _record_history(
        self,
        event_type: str,
        title: Optional[str],
        body: Optional[str],
        target: Optional[str],
        result: NotificationDispatchResult,
    ) -> None:
        try:
            payload = result.model_dump()
            categories = payload.get("categories") or {}
            with Session(self._engine) as session:
                crud.log_notification_event(
                    session,
                    event_type=event_type,
                    title=title,
                    body=body,
                    target=target,
                    sent=bool(result.sent),
                    response_message=result.message,
                    categories=categories,
                )
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to record notification history")
