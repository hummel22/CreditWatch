from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import smbclient
from fastapi import FastAPI
from sqlmodel import Session

from . import crud
from .database import DATABASE_PATH

logger = logging.getLogger("creditwatch.backup")


@dataclass
class BackupConfig:
    id: int
    server: str
    share: str
    directory: str
    username: str
    password: str
    domain: Optional[str]


class BackupService:
    """Background service that coordinates automated SMB backups."""

    def __init__(self, *, engine) -> None:
        self._engine = engine
        self._task: asyncio.Task[None] | None = None
        self._event = asyncio.Event()
        self._last_change: datetime | None = None
        self._next_run: datetime | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    def register_change(self) -> None:
        """Mark that the database content has changed."""

        self._last_change = datetime.utcnow()
        self._event.set()

    def refresh_settings(self) -> None:
        """Signal that settings have changed and should be reloaded."""

        self._event.set()

    @property
    def next_run(self) -> datetime | None:
        return self._next_run

    async def _run(self) -> None:
        while True:
            await self._event.wait()
            self._event.clear()
            while True:
                config = await asyncio.to_thread(self._load_config)
                change = self._last_change
                if config is None or change is None:
                    self._next_run = None
                    break
                due_at = change + timedelta(hours=1)
                now = datetime.utcnow()
                wait_seconds = (due_at - now).total_seconds()
                if wait_seconds <= 0:
                    try:
                        await asyncio.to_thread(self._perform_backup, config)
                    except Exception:  # pragma: no cover - defensive logging
                        logger.exception("Automated backup failed")
                    finally:
                        self._last_change = None
                        self._next_run = None
                    break
                self._next_run = due_at
                try:
                    await asyncio.wait_for(self._event.wait(), timeout=wait_seconds)
                except asyncio.TimeoutError:
                    continue
                else:
                    self._event.clear()

    def _load_config(self) -> BackupConfig | None:
        with Session(self._engine) as session:
            settings = crud.get_backup_settings(session)
            if settings is None or not settings.password:
                return None
            return BackupConfig(
                id=settings.id or 1,
                server=settings.server,
                share=settings.share,
                directory=settings.directory or "",
                username=settings.username,
                password=settings.password,
                domain=settings.domain,
            )

    async def run_backup_now(self) -> None:
        """Execute a backup immediately using the current configuration."""

        config = await asyncio.to_thread(self._load_config)
        if config is None:
            raise RuntimeError("Backup settings have not been configured.")
        await asyncio.to_thread(self._perform_backup, config)
        self._last_change = None
        self._next_run = None
        self._event.clear()

    def test_connection(self, config: BackupConfig) -> None:
        """Validate that the provided configuration can access the SMB share."""

        self._verify_connection(config)

    def _perform_backup(self, config: BackupConfig) -> None:
        timestamp = datetime.utcnow()
        filename = f"creditwatch-{timestamp:%Y-%m}.db"
        temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        temp_file = Path(temp_path)
        try:
            self._export_sqlite(temp_file)
            self._upload_to_smb(config, temp_file, filename)
        except Exception as exc:
            with Session(self._engine) as session:
                settings = crud.get_backup_settings(session)
                if settings and (settings.id or 1) == config.id:
                    crud.record_backup_failure(session, settings, str(exc))
            raise
        else:
            with Session(self._engine) as session:
                settings = crud.get_backup_settings(session)
                if settings and (settings.id or 1) == config.id:
                    crud.record_backup_success(
                        session, settings, timestamp=timestamp, filename=filename
                    )
        finally:
            try:
                temp_file.unlink()
            except FileNotFoundError:
                pass

    def _export_sqlite(self, destination: Path) -> None:
        source_path = DATABASE_PATH / "creditwatch.db"
        if not source_path.exists():
            raise FileNotFoundError("CreditWatch database has not been created yet.")
        with sqlite3.connect(source_path) as source, sqlite3.connect(destination) as target:
            source.backup(target)

    def _upload_to_smb(self, config: BackupConfig, source: Path, filename: str) -> None:
        smbclient.reset_connection_cache()
        remote_base, remote_dir, _ = self._resolve_remote_paths(config)
        remote_path = f"{remote_dir}/{filename}"
        self._register_session(config)
        smbclient.makedirs(remote_dir, exist_ok=True)
        with smbclient.open_file(remote_path, mode="wb", buffering=0) as remote_file:
            with source.open("rb") as local_file:
                while True:
                    chunk = local_file.read(1024 * 1024)
                    if not chunk:
                        break
                    remote_file.write(chunk)
        smbclient.reset_connection_cache()

    def _verify_connection(self, config: BackupConfig) -> None:
        smbclient.reset_connection_cache()
        remote_base, remote_dir, directory = self._resolve_remote_paths(config)
        try:
            self._register_session(config)
            target_path = remote_dir if directory else remote_base
            try:
                smbclient.listdir(target_path)
            except FileNotFoundError as exc:
                raise FileNotFoundError(
                    "The specified directory could not be found on the SMB share."
                ) from exc
        finally:
            smbclient.reset_connection_cache()

    def _resolve_remote_paths(self, config: BackupConfig) -> tuple[str, str, str]:
        remote_base = f"//{config.server}/{config.share}"
        directory = config.directory.replace("\\", "/").strip("/")
        remote_dir = f"{remote_base}/{directory}" if directory else remote_base
        return remote_base, remote_dir, directory

    def _register_session(self, config: BackupConfig) -> None:
        credentials = {
            "username": config.username,
            "password": config.password,
        }
        domain = (config.domain or "").strip()
        if domain:
            credentials["domain"] = domain
        smbclient.register_session(config.server, **credentials)


def schedule_backup_after_change(app: FastAPI) -> None:
    service: BackupService | None = getattr(app.state, "backup_service", None)
    if service is not None:
        service.register_change()


def refresh_backup_settings(app: FastAPI) -> None:
    service: BackupService | None = getattr(app.state, "backup_service", None)
    if service is not None:
        service.refresh_settings()
