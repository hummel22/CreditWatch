from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlmodel import Session

from . import crud
from .database import DATABASE_PATH
from .google_drive import GoogleDriveBackupClient

logger = logging.getLogger("creditwatch.backups")


@dataclass
class BackupResult:
    """Structured result of a backup execution."""

    success: bool
    message: str
    timestamp: datetime
    file_id: Optional[str] = None
    file_name: Optional[str] = None
    size_bytes: Optional[int] = None


class BackupService:
    """Coordinate delayed database backups with Google Drive."""

    def __init__(self, *, engine, delay: timedelta | None = None) -> None:
        self._engine = engine
        self._delay = delay or timedelta(hours=1)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._scheduled_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._configured = False
        self._next_run_at: datetime | None = None
        self._last_result: BackupResult | None = None

    # ------------------------------------------------------------------
    # Lifecycle management
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Capture the running event loop for future scheduling."""

        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:  # pragma: no cover - defensive guard
            self._loop = asyncio.get_event_loop()
        logger.debug("Backup service initialised")

    async def stop(self) -> None:
        """Cancel any pending backup tasks and wait for them to exit."""

        if self._scheduled_task is None:
            return
        self._scheduled_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._scheduled_task
        self._scheduled_task = None
        self._next_run_at = None

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    def refresh_configuration(self) -> None:
        """Load configuration state from the database."""

        with Session(self._engine) as session:
            settings = crud.get_backup_settings(session)
        self._configured = bool(settings and settings.is_configured)
        logger.debug("Backup service configuration updated: %s", self._configured)

    def apply_settings_change(self, configured: bool) -> None:
        """Update the in-memory configuration flag."""

        self._configured = configured

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def notify_change(self) -> None:
        """Schedule a backup after the configured delay."""

        if not self._configured:
            logger.debug("Backup configuration incomplete; skipping schedule request")
            return
        if self._loop is None:
            logger.debug("Backup service loop not ready; change ignored")
            return
        self._loop.call_soon_threadsafe(self._schedule_backup)

    async def run_immediately(self) -> BackupResult:
        """Execute a backup immediately."""

        if not self._configured:
            now = datetime.utcnow()
            result = BackupResult(
                success=False,
                message="Backup configuration is incomplete.",
                timestamp=now,
            )
            self._last_result = result
            return result
        await self._cancel_pending()
        return await self._perform_backup()

    def get_status(self) -> dict[str, Optional[datetime]]:
        """Return transient runtime information for API responses."""

        return {
            "next_run_at": self._next_run_at,
            "last_result": self._last_result,
        }

    # ------------------------------------------------------------------
    # Internal helpers executed on the event loop
    # ------------------------------------------------------------------
    def _schedule_backup(self) -> None:
        if self._scheduled_task is not None:
            self._scheduled_task.cancel()
        delay_seconds = max(self._delay.total_seconds(), 0)
        self._next_run_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
        self._scheduled_task = asyncio.create_task(self._delayed_backup(delay_seconds))
        logger.debug(
            "Scheduled next database backup for %s", self._next_run_at.isoformat()
        )

    async def _delayed_backup(self, delay_seconds: float) -> None:
        try:
            await asyncio.sleep(delay_seconds)
            await self._perform_backup()
        except asyncio.CancelledError:
            logger.debug("Backup timer cancelled")
            raise
        except Exception:  # pragma: no cover - defensive guard
            logger.exception("Unhandled exception while running scheduled backup")
        finally:
            self._scheduled_task = None
            self._next_run_at = None

    async def _cancel_pending(self) -> None:
        if self._scheduled_task is None:
            return
        self._scheduled_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._scheduled_task
        self._scheduled_task = None
        self._next_run_at = None

    async def _perform_backup(self) -> BackupResult:
        async with self._lock:
            try:
                result = await asyncio.to_thread(self._execute_backup)
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.exception("Database backup failed")
                result = BackupResult(
                    success=False,
                    message=str(exc),
                    timestamp=datetime.utcnow(),
                )
            self._last_result = result
            return result

    # ------------------------------------------------------------------
    # Blocking backup implementation executed in a worker thread
    # ------------------------------------------------------------------
    def _execute_backup(self) -> BackupResult:
        database_path = Path(DATABASE_PATH) / "creditwatch.db"
        now = datetime.utcnow()
        if not database_path.exists():
            message = f"Database file not found at {database_path}".rstrip()
            logger.warning(message)
            return BackupResult(success=False, message=message, timestamp=now)

        with Session(self._engine) as session:
            settings = crud.get_backup_settings(session)
            if settings is None or not settings.is_configured:
                message = "Backup configuration is incomplete."
                logger.warning(message)
                return BackupResult(success=False, message=message, timestamp=now)

            client = GoogleDriveBackupClient.from_serialised_credentials(
                folder_id=settings.drive_folder_id,
                service_account_json=settings.service_account_json,
            )

            file_name = f"creditwatch-backup-{now:%Y-%m}.db"
            drive_result = client.upload_backup(source=database_path, target_name=file_name)

            settings.last_backup_at = now
            settings.last_backup_file_id = drive_result.file_id
            settings.last_backup_filename = drive_result.file_name
            settings.last_backup_size = drive_result.size_bytes
            settings.last_backup_error = None
            settings.updated_at = now

            crud.save_backup_settings(session, settings)

        return BackupResult(
            success=True,
            message="Backup uploaded successfully.",
            timestamp=now,
            file_id=drive_result.file_id,
            file_name=drive_result.file_name,
            size_bytes=drive_result.size_bytes,
        )
