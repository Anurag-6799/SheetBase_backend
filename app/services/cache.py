"""Redis cache-aside layer.

Google's Sheets API is both slow (hundreds of ms) and aggressively rate limited,
so every read that can be served from Redis should be. Every function here fails
open: if Redis is unreachable the caller still gets its data from Google, just
slower. A cache outage must degrade latency, never availability.
"""
import asyncio
import json
import logging
from typing import Any, List, Optional

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Optional[redis.Redis] = None
_client_loop: Optional[asyncio.AbstractEventLoop] = None


def get_client() -> redis.Redis:
    """Return the shared connection pool, rebuilding it if the loop changed.

    A redis.asyncio client binds to the event loop it was created on. If that
    loop goes away the client does not raise loudly - every call fails with
    "Event loop is closed", which our fail-open error handling then swallows as
    a cache miss. The result is a cache that is silently never used. Tracking
    the loop costs two lines and removes that failure mode entirely.
    """
    global _client, _client_loop
    loop = asyncio.get_running_loop()
    if _client is None or _client_loop is not loop:
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        _client_loop = loop
    return _client


async def close_client() -> None:
    global _client, _client_loop
    if _client is not None:
        await _client.aclose()
        _client = None
        _client_loop = None


def cache_key(api_id: str) -> str:
    return f"sheetbase:api:{api_id}"


async def get_records(api_id: str) -> Optional[List[Any]]:
    """Return cached records, or None on a miss / any Redis problem."""
    try:
        raw = await get_client().get(cache_key(api_id))
    except Exception as exc:  # noqa: BLE001 - degrade, never fail the request
        logger.warning("cache read failed for %s, serving from source: %s", api_id, exc)
        return None
    return json.loads(raw) if raw else None


async def set_records(api_id: str, records: List[Any]) -> None:
    try:
        await get_client().set(
            cache_key(api_id), json.dumps(records), ex=settings.CACHE_TTL_SECONDS
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache write failed for %s: %s", api_id, exc)


async def invalidate(api_id: str) -> None:
    """Drop a cached sheet so the next read goes back to Google."""
    try:
        await get_client().delete(cache_key(api_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache invalidation failed for %s: %s", api_id, exc)
