"""Google Drive + Sheets reads.

The Google client libraries are synchronous, so every call here is pushed to a
worker thread rather than blocking the event loop.
"""
from typing import Any, Dict, List

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.security import decrypt_token
from app.services.google_auth import SCOPES

TOKEN_URI = "https://oauth2.googleapis.com/token"


def build_credentials(encrypted_refresh_token: str) -> Credentials:
    """Rebuild usable credentials from the refresh token we stored at login.

    Access tokens last an hour; the refresh token is the durable one, which is
    why it is the thing kept encrypted at rest. google-auth performs the refresh
    on first use.
    """
    return Credentials(
        token=None,
        refresh_token=decrypt_token(encrypted_refresh_token),
        token_uri=TOKEN_URI,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )


def _list_spreadsheets_sync(creds: Credentials, page_size: int) -> List[Dict[str, str]]:
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    response = (
        service.files()
        .list(
            q="mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
            pageSize=page_size,
            fields="files(id, name, modifiedTime)",
            orderBy="modifiedTime desc",
        )
        .execute()
    )
    return response.get("files", [])


async def list_spreadsheets(creds: Credentials, page_size: int = 50) -> List[Dict[str, str]]:
    """The user's spreadsheets, most recently modified first."""
    return await run_in_threadpool(_list_spreadsheets_sync, creds, page_size)


def _get_values_sync(creds: Credentials, spreadsheet_id: str, sheet_name: str) -> List[List[Any]]:
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    response = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=sheet_name)
        .execute()
    )
    return response.get("values", [])


async def get_values(creds: Credentials, spreadsheet_id: str, sheet_name: str) -> List[List[Any]]:
    """Raw cell values for one tab, header row included."""
    return await run_in_threadpool(_get_values_sync, creds, spreadsheet_id, sheet_name)


def _get_tab_names_sync(creds: Credentials, spreadsheet_id: str) -> List[str]:
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    meta = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(title))")
        .execute()
    )
    return [s["properties"]["title"] for s in meta.get("sheets", [])]


async def get_tab_names(creds: Credentials, spreadsheet_id: str) -> List[str]:
    """Tab titles within a spreadsheet, so a caller can pick one to expose."""
    return await run_in_threadpool(_get_tab_names_sync, creds, spreadsheet_id)
