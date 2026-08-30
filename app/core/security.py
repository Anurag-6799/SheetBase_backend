from cryptography.fernet import Fernet
from app.core.config import settings

# Initialize the cipher suite using the key from .env file
cipher_suite = Fernet(settings.ENCRYPTION_KEY.encode())

def encrypt_token(token: str) -> str:
    """Encrypts a raw string into a secure byte string, stored as text."""
    return cipher_suite.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    """Decrypts the database text back into the raw token string."""
    return cipher_suite.decrypt(encrypted_token.encode()).decode()


# --- Session tokens -------------------------------------------------------
# Fernet is already the project's crypto primitive and it is authenticated
# encryption with an embedded timestamp, so it gives us opaque, tamper-proof,
# expiring session tokens without pulling in a JWT dependency. The payload is
# just the user id - nothing secret, but nothing forgeable either.

SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 7  # 7 days


def create_session_token(user_id: int) -> str:
    """Issue a session token for a freshly authenticated user."""
    return cipher_suite.encrypt(str(user_id).encode()).decode()


def read_session_token(token: str) -> int:
    """Return the user id, or raise if the token is forged or expired."""
    raw = cipher_suite.decrypt(token.encode(), ttl=SESSION_MAX_AGE_SECONDS)
    return int(raw.decode())