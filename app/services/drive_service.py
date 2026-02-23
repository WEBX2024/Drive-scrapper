# drive_service.py — Google Drive OAuth2 auth, file listing with pagination, and downloading

import io
import logging
from pathlib import Path
from typing import Any

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from app.config import settings, DOWNLOAD_DIR
from app.utils.file_utils import ensure_directory, get_file_extension

logger = logging.getLogger(__name__)

# Supported MIME types ↔ file extensions
SUPPORTED_MIME_MAP: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
}

SUPPORTED_EXTENSIONS: set[str] = set(SUPPORTED_MIME_MAP.values())

# Read-only Drive API scope
_SCOPES: list[str] = ["https://www.googleapis.com/auth/drive.readonly"]


# OAuth2 helpers

def _build_flow() -> Flow:
    """Build a Google OAuth2 flow from environment config."""
    client_config: dict[str, Any] = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=_SCOPES)
    flow.redirect_uri = settings.google_redirect_uri
    return flow


def get_auth_url() -> str:
    """Generate the Google OAuth2 authorization URL."""
    flow = _build_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    logger.info("Generated OAuth2 authorization URL.")
    return auth_url


def exchange_code(code: str) -> Credentials:
    """Exchange an OAuth2 authorization code for credentials."""
    flow = _build_flow()
    flow.fetch_token(code=code)
    logger.info("OAuth2 token exchange successful.")
    return flow.credentials


# Drive operations

def _get_drive_service(credentials: Credentials):
    """Build an authorised Drive v3 API service client."""
    return build("drive", "v3", credentials=credentials)


def list_files(credentials: Credentials) -> list[dict[str, str]]:
    """List all supported files from Drive with pagination and a safety cap."""
    service = _get_drive_service(credentials)
    max_cap: int = settings.max_files_cap

    # Build MIME-type query filter
    mime_clauses = " or ".join(
        f"mimeType='{mime}'" for mime in SUPPORTED_MIME_MAP
    )
    query = f"({mime_clauses}) and trashed=false"

    all_files: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    page_token: str | None = None

    while True:
        response = (
            service.files()
            .list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id, name, mimeType)",
                pageToken=page_token,
                pageSize=min(100, max_cap - len(all_files)),
            )
            .execute()
        )

        for f in response.get("files", []):
            file_id: str = f["id"]
            if file_id in seen_ids:
                continue
            seen_ids.add(file_id)
            all_files.append(
                {"id": file_id, "name": f["name"], "mimeType": f["mimeType"]}
            )

            # Safety cap check
            if len(all_files) >= max_cap:
                logger.warning(
                    "Safety cap reached (%d files). Stopping file listing.", max_cap
                )
                break

        if len(all_files) >= max_cap:
            break

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    logger.info(
        "Listed %d supported file(s) across entire Drive (cap=%d).",
        len(all_files), max_cap,
    )
    return all_files


def download_file(credentials: Credentials, file_id: str, file_name: str) -> str:
    """Download a single file from Drive to the local downloads directory."""
    ext = get_file_extension(file_name)
    if ext not in SUPPORTED_EXTENSIONS:
        raise RuntimeError(
            f"Unsupported file extension '.{ext}' for file '{file_name}'."
        )

    ensure_directory(DOWNLOAD_DIR)
    dest_path: Path = DOWNLOAD_DIR / file_name

    service = _get_drive_service(credentials)
    request = service.files().get_media(fileId=file_id)

    with open(dest_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                logger.debug(
                    "Downloading %s — %d%%", file_name, int(status.progress() * 100)
                )

    logger.info("Downloaded '%s' → %s", file_name, dest_path)
    return str(dest_path)
