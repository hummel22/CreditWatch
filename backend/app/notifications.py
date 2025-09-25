from __future__ import annotations

import asyncio
import calendar
import logging
from contextlib import suppress
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional

import httpx
from sqlmodel import Session, select

from . import crud
from .models import Benefit, CreditCard, NotificationSettings
from .schemas import (
    NotificationBenefitSummary,
    NotificationDispatchResult,
)

logger = logging.getLogger("creditwatch.notifications")


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
        return await self._send_payload(
            settings,
            title or "CreditWatch notification",
            message,
            {},
            target_override=target_override,
        )

    async def send_daily_notifications(
        self, target_date: Optional[date] = None, *, target_override: Optional[str] = None
    ) -> NotificationDispatchResult:
        """Compute and dispatch the daily reminder notification if required."""

        target = target_date or date.today()
        with Session(self._engine) as session:
            categories = self._collect_categories(session, target)
            settings = crud.get_notification_settings(session)
        if not categories:
            result = NotificationDispatchResult(
                sent=False,
                message="No expiring benefits to report.",
                categories={},
            )
        else:
            title = f"CreditWatch reminders for {target.strftime('%B %d, %Y')}"
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
    ) -> Dict[str, List[NotificationBenefitSummary]]:
        categories: Dict[str, List[NotificationBenefitSummary]] = {}
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
        return categories

    def _fetch_benefits(
        self, session: Session, start: date, end: date
    ) -> List[NotificationBenefitSummary]:
        statement = (
            select(Benefit, CreditCard)
            .join(CreditCard, CreditCard.id == Benefit.credit_card_id)
            .where(Benefit.expiration_date.is_not(None))
            .where(Benefit.expiration_date >= start)
            .where(Benefit.expiration_date <= end)
            .order_by(Benefit.expiration_date, CreditCard.card_name, Benefit.name)
        )
        results: List[NotificationBenefitSummary] = []
        for benefit, card in session.exec(statement).all():
            results.append(
                NotificationBenefitSummary(
                    card_name=card.card_name,
                    benefit_name=benefit.name,
                    expiration_date=benefit.expiration_date,
                )
            )
        return results

    def _render_daily_body(
        self, target: date, categories: Dict[str, List[NotificationBenefitSummary]]
    ) -> str:
        sections: List[str] = []
        month_section = categories.get("expiring_this_month")
        if month_section:
            sections.append(
                "Benefits expiring this month:\n" + "\n".join(self._format_line(item) for item in month_section)
            )
        ten_day_section = categories.get("expiring_in_10_days")
        if ten_day_section:
            sections.append(
                "Benefits expiring in 10 days:\n" + "\n".join(self._format_line(item) for item in ten_day_section)
            )
        today_section = categories.get("expiring_today")
        if today_section:
            sections.append(
                "Benefits expiring today:\n" + "\n".join(self._format_line(item) for item in today_section)
            )
        return "\n\n".join(sections)

    def _format_line(self, summary: NotificationBenefitSummary) -> str:
        return f"- {summary.benefit_name} ({summary.card_name}) – {summary.expiration_date:%b %d}" \
            if summary.expiration_date else f"- {summary.benefit_name} ({summary.card_name})"

    async def _send_payload(
        self,
        settings: NotificationSettings | None,
        title: str,
        message: str,
        categories: Dict[str, List[NotificationBenefitSummary]],
        *,
        target_override: Optional[str] = None,
    ) -> NotificationDispatchResult:
        if settings is None:
            return NotificationDispatchResult(
                sent=False,
                message="Notification settings have not been configured.",
                categories=categories,
            )
        if not settings.enabled:
            return NotificationDispatchResult(
                sent=False,
                message="Notifications are currently disabled.",
                categories=categories,
            )
        payload = {"title": title, "message": message}
        target = target_override or settings.default_target
        if target:
            payload["target"] = target
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
            )
        return NotificationDispatchResult(
            sent=True,
            message="Notification delivered successfully.",
            categories=categories,
        )
