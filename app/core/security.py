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