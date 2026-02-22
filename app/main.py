from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

def get_application() -> FastAPI:
    """
    Initializes and configures the core FastAPI application.
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        description="High-performance REST API generator for Google Sheets."
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
