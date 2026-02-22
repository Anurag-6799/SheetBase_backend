from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "SheetBase API"
    API_V1_STR: str = "/api/v1"
    
    SECRET_KEY: str
    ENCRYPTION_KEY: str
    
    BACKEND_CORS_ORIGINS: List[str] = []

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()