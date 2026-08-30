"""Shared FastAPI dependencies."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.security import read_session_token
from app.db.session import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the caller from their session token.

    Used to guard the management endpoints. The published data endpoints are
    deliberately unauthenticated - that is the whole point of publishing one.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        user_id = read_session_token(credentials.credentials)
    except Exception:  # noqa: BLE001 - invalid, tampered or expired all look alike to the caller
        raise unauthorized

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if user is None:
        raise unauthorized
    return user


def require_google_link(user: User) -> str:
    """Ensure we still hold a refresh token for this user before calling Google."""
    if not user.encrypted_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Google account is not linked. Sign in again at /api/v1/auth/login.",
        )
    return user.encrypted_refresh_token
