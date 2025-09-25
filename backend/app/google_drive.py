from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger("creditwatch.backups.google_drive")

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


@dataclass
class GoogleDriveBackupResult:
    """Result payload returned after uploading a backup."""

    file_id: str
    file_name: str
    size_bytes: int


class GoogleDriveBackupClient:
    """Thin wrapper for interacting with the Google Drive API."""

    def __init__(self, *, folder_id: str, service_account_info: dict) -> None:
        if not folder_id:
            raise ValueError("A Google Drive folder ID is required.")
        if not service_account_info:
            raise ValueError("Service account credentials are required.")
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES
        )
        self._folder_id = folder_id
        self._service = build(
            "drive",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )

    @classmethod
    def from_serialised_credentials(
        cls, *, folder_id: str, service_account_json: str
    ) -> "GoogleDriveBackupClient":
        try:
            data = json.loads(service_account_json)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
            raise ValueError("Invalid Google service account JSON provided.") from exc
        return cls(folder_id=folder_id, service_account_info=data)

    def upload_backup(self, *, source: Path, target_name: str) -> GoogleDriveBackupResult:
        """Upload the provided SQLite database to Drive.

        If a file with ``target_name`` already exists in the configured folder it will
        be replaced, otherwise a new file will be created.
        """

        if not source.exists():
            raise FileNotFoundError(f"Backup source file not found: {source}")

        media = MediaFileUpload(
            str(source), mimetype="application/x-sqlite3", resumable=False
        )
        query = (
            f"name = '{target_name}' and '{self._folder_id}' in parents and trashed = false"
        )
        existing_file_id: Optional[str] = None
        try:
            response = (
                self._service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="files(id, name)",
                    pageSize=1,
                )
                .execute()
            )
        except HttpError:  # pragma: no cover - network failure guard
            logger.exception("Failed to query existing Google Drive backups")
            raise
        files = response.get("files", [])
        if files:
            existing_file_id = files[0].get("id")

        try:
            if existing_file_id:
                file_metadata = {"name": target_name}
                update_request = self._service.files().update(
                    fileId=existing_file_id,
                    media_body=media,
                    body=file_metadata,
                )
                result = update_request.execute()
                file_id = result["id"]
            else:
                file_metadata = {
                    "name": target_name,
                    "parents": [self._folder_id],
                }
                create_request = self._service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields="id, name",
                )
                result = create_request.execute()
                file_id = result["id"]
        except HttpError:
            logger.exception("Failed to upload Google Drive backup")
            raise

        size_bytes = source.stat().st_size
        return GoogleDriveBackupResult(
            file_id=file_id,
            file_name=target_name,
            size_bytes=size_bytes,
        )


def extract_service_account_email(service_account_json: str) -> Optional[str]:
    """Attempt to read the service account's email from the JSON payload."""

    try:
        payload = json.loads(service_account_json)
    except json.JSONDecodeError:
        return None
    email = payload.get("client_email")
    if not isinstance(email, str):
        return None
    return email
