from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.api.v1 import auth, apis, data
from app.services import cache

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await cache.close_client()

def get_application() -> FastAPI:
    """
    Initializes and configures the core FastAPI application.
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        description="High-performance REST API generator for Google Sheets.",
        lifespan=lifespan
    )

    # Configure CORS (Cross-Origin Resource Sharing)
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.BACKEND_CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    return app

app = get_application()


@app.get("/health", tags=["System"])
async def health_check():
    """
    Used by AWS, Render, or Docker to verify the container is alive and routing traffic.
    """
    return {
        "status": "healthy", 
        "service": settings.PROJECT_NAME
    }

app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
app.include_router(apis.router, prefix=settings.API_V1_STR, tags=["API Management"])
app.include_router(data.router, prefix=f"{settings.API_V1_STR}/data", tags=["Published Data"])

# Serve the dashboard from the same origin as the API. Mounted last so every
# route above still wins, and same-origin is what lets the Google OAuth callback
# redirect straight back into the app instead of leaving JSON on the screen.
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
