"""Management endpoints: browse your sheets, publish one as an API, unpublish it.

Everything here requires a session token. The published endpoints themselves
live in api/v1/data.py and are public.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.deps import get_current_user, require_google_link
from app.db.session import get_db
from app.models.sheet_api import SheetApi
from app.models.user import User
from app.services import cache, sheets

router = APIRouter()


class PublishRequest(BaseModel):
    spreadsheet_id: str
    sheet_name: str = "Sheet1"
    title: Optional[str] = None


class SheetApiResponse(BaseModel):
    id: str
    spreadsheet_id: str
    sheet_name: str
    title: Optional[str]
    is_active: bool
    endpoint: str

    @classmethod
    def of(cls, api: SheetApi) -> "SheetApiResponse":
        return cls(
            id=api.id,
            spreadsheet_id=api.spreadsheet_id,
            sheet_name=api.sheet_name,
            title=api.title,
            is_active=api.is_active,
            endpoint=f"/api/v1/data/{api.id}",
        )


@router.get("/sheets", summary="List the spreadsheets in your Drive")
async def list_sheets(user: User = Depends(get_current_user)):
    creds = sheets.build_credentials(require_google_link(user))
    return await sheets.list_spreadsheets(creds)


@router.get("/sheets/{spreadsheet_id}/tabs", summary="List the tabs in one spreadsheet")
async def list_tabs(spreadsheet_id: str, user: User = Depends(get_current_user)):
    creds = sheets.build_credentials(require_google_link(user))
    return {"spreadsheet_id": spreadsheet_id, "tabs": await sheets.get_tab_names(creds, spreadsheet_id)}


@router.post("/apis", status_code=status.HTTP_201_CREATED, summary="Publish a sheet as a REST API")
async def publish_api(
    payload: PublishRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SheetApiResponse:
    """Publishing is idempotent: re-publishing the same tab returns the existing
    endpoint rather than minting a second URL for identical data."""
    existing = await db.execute(
        select(SheetApi).where(
            SheetApi.user_id == user.id,
            SheetApi.spreadsheet_id == payload.spreadsheet_id,
            SheetApi.sheet_name == payload.sheet_name,
        )
    )
    api = existing.scalars().first()
    if api:
        if not api.is_active:
            api.is_active = True
            await db.commit()
            await db.refresh(api)
        return SheetApiResponse.of(api)

    # Fail here rather than at first read: publishing a sheet we cannot open
    # would hand the user a URL that 502s later, with no clue why.
    creds = sheets.build_credentials(require_google_link(user))
    try:
        await sheets.get_values(creds, payload.spreadsheet_id, payload.sheet_name)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read that sheet: {exc}",
        )

    api = SheetApi(
        user_id=user.id,
        spreadsheet_id=payload.spreadsheet_id,
        sheet_name=payload.sheet_name,
        title=payload.title,
    )
    db.add(api)
    await db.commit()
    await db.refresh(api)
    return SheetApiResponse.of(api)


@router.get("/apis", summary="List your published APIs")
async def list_apis(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[SheetApiResponse]:
    result = await db.execute(
        select(SheetApi).where(SheetApi.user_id == user.id).order_by(SheetApi.created_at.desc())
    )
    return [SheetApiResponse.of(a) for a in result.scalars().all()]


@router.post("/apis/{api_id}/refresh", summary="Drop the cache for one API")
async def refresh_api(
    api_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Invalidate on demand, for when the sheet changed and the caller does not
    want to wait out the TTL."""
    api = await _owned_api(db, api_id, user)
    await cache.invalidate(api.id)
    return {"status": "cache cleared", "api_id": api.id}


@router.delete("/apis/{api_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Unpublish an API")
async def delete_api(
    api_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    api = await _owned_api(db, api_id, user)
    # Clear the cache first: a deleted endpoint must not keep serving rows from
    # Redis for the rest of the TTL.
    await cache.invalidate(api.id)
    await db.delete(api)
    await db.commit()


async def _owned_api(db: AsyncSession, api_id: str, user: User) -> SheetApi:
    result = await db.execute(
        select(SheetApi).where(SheetApi.id == api_id, SheetApi.user_id == user.id)
    )
    api = result.scalars().first()
    if api is None:
        # Same response whether it does not exist or belongs to someone else -
        # no probing for other people's endpoint ids.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API not found")
    return api
