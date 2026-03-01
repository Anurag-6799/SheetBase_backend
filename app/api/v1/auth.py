from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from app.services.google_auth import generate_auth_url

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
async def callback(code: str):
    """
    Google sends the user back here with a temporary 'code' in the URL.
    (We will exchange this code for the Refresh Token in the next step).
    """
    return {
        "message": "Authorization Code Received!", 
        "code": code
    }