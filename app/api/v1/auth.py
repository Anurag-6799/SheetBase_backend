from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.models.user import User
from app.services.google_auth import generate_auth_url, exchange_code_for_tokens
from app.core.security import encrypt_token, create_session_token

router = APIRouter()

@router.get("/login", summary="Initiate Google Login")
async def login():
    """
    Generates the Google OAuth URL and immediately redirects the user to it.
    """
    auth_url = generate_auth_url()
    # We use a RedirectResponse so the browser automatically jumps to Google
    return RedirectResponse(url=auth_url)


@router.get("/callback", summary="Google OAuth Callback")
async def callback(code: str, db: AsyncSession = Depends(get_db)):
    """
    Completes the OAuth flow and Upserts the user into the database.
    """
    try:
        # Exchanging code for Google credentials
        google_data = exchange_code_for_tokens(code)
        email = google_data["email"]
        raw_refresh_token = google_data.get("refresh_token")
        
        # Checking if user already exists in Postgres
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        
        if user:
            if raw_refresh_token:
                user.encrypted_refresh_token = encrypt_token(raw_refresh_token)
        else:
            # Creating a new user
            encrypted_token = encrypt_token(raw_refresh_token) if raw_refresh_token else None
            user = User(
                email=email,
                encrypted_refresh_token=encrypted_token
            )
            db.add(user)
            
        # Committing the transaction to the database
        await db.commit()
        await db.refresh(user)
        
        # Hand the session token back to the dashboard in the URL *fragment*.
        # A fragment is never sent to a server, so the token stays out of access
        # logs, proxies and Referer headers - unlike a query parameter.
        # The management endpoints then take it as `Authorization: Bearer <token>`.
        token = create_session_token(user.id)
        return RedirectResponse(url=f"/#token={token}")
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))