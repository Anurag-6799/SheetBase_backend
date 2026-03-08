import requests

from google_auth_oauthlib.flow import Flow
from app.core.config import settings
from google.oauth2.credentials import Credentials

# We need basic profile info, plus read-only access to Drive and Sheets.
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly"
]

def get_google_oauth_flow() -> Flow:
    """
    Constructs the OAuth flow object securely using in-memory environment variables
    instead of a downloaded JSON file.
    """
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "project_id": "sheetbase",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI
    )
    return flow

def generate_auth_url() -> str:
    """
    Generates the strict URL that we will redirect the user to.
    """
    flow = get_google_oauth_flow()
    
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true"
    )
    
    return authorization_url


def exchange_code_for_tokens(code: str) -> dict:
    """
    Exchanges the temporary code for permanent tokens.
    """
    flow = get_google_oauth_flow()
    
    # This makes the silent HTTP POST request to Google's backend
    flow.fetch_token(code=code)
    credentials = flow.credentials
    
    # Now we use the temporary access token to ask Google for the user's email
    user_info_response = requests.get(
        "https://www.googleapis.com/oauth2/v1/userinfo",
        headers={"Authorization": f"Bearer {credentials.token}"}
    )
    user_info = user_info_response.json()
    
    return {
        "email": user_info["email"],
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
    }

