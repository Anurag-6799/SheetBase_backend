"""The published, public endpoint - the actual product.

GET /api/v1/data/{api_id}
    ?columns=Name,Price      project only these columns
    &limit=50&offset=10      paginate
    &order_by=Price&order=desc
    &<column>=<value>        filter by equality on any column

Reads are cache-aside: Redis first, Google only on a miss.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.models.sheet_api import SheetApi
from app.models.user import User
from app.services import cache, sheets
from app.services.transform import apply_query, parse_filters, rows_to_records

router = APIRouter()


@router.get("/{api_id}", summary="Read a published sheet as JSON")
async def read_api(
    api_id: str,
    request: Request,
    columns: str | None = Query(None, description="Comma-separated column names"),
    limit: int | None = Query(None, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    order_by: str | None = Query(None),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SheetApi).where(SheetApi.id == api_id, SheetApi.is_active.is_(True))
    )
    api = result.scalars().first()
    if api is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API not found")

    records, source = await _load_records(api, db)

    selected = [c.strip() for c in columns.split(",") if c.strip()] if columns else None
    rows = apply_query(
        records,
        columns=selected,
        filters=parse_filters(dict(request.query_params)),
        order_by=order_by,
        descending=(order == "desc"),
        limit=limit,
        offset=offset,
    )

    return {
        "api_id": api.id,
        "source": source,          # "cache" or "google" - handy when debugging staleness
        "total": len(records),     # before filtering/pagination
        "count": len(rows),
        "data": rows,
    }


async def _load_records(api: SheetApi, db: AsyncSession):
    """Cache-aside: Redis, then Google, then populate the cache."""
    cached = await cache.get_records(api.id)
    if cached is not None:
        return cached, "cache"

    owner = (await db.execute(select(User).where(User.id == api.user_id))).scalars().first()
    if owner is None or not owner.encrypted_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The owner of this API needs to re-link their Google account.",
        )

    creds = sheets.build_credentials(owner.encrypted_refresh_token)
    try:
        values = await sheets.get_values(creds, api.spreadsheet_id, api.sheet_name)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream Google Sheets read failed: {exc}",
        )

    records = rows_to_records(values)
    await cache.set_records(api.id, records)
    return records, "google"
