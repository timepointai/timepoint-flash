"""FastAPI application for TIMEPOINT Flash.

This module provides the main FastAPI application with health endpoints,
API routes, and lifecycle management.

Run with:
    uvicorn app.main:app --reload

Examples:
    >>> # Health check
    >>> curl http://localhost:8000/health

    >>> # API docs
    >>> # Open http://localhost:8000/docs

Tests:
    - tests/unit/test_main.py::test_health_endpoint
    - tests/integration/test_api.py::test_api_routes
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app import __version__
from app.api.v1 import router as v1_router
from app.config import get_settings, validate_presets_or_raise
from app.database import check_db_connection, close_db, init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Response models
class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    database: bool
    providers: dict[str, bool]


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str
    detail: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown tasks:
    - Validate model configurations on startup
    - Initialize database on startup
    - Close connections on shutdown
    """
    # Startup
    logger.info(f"Starting TIMEPOINT Flash v{__version__}")

    # Validate presets use only verified models
    # This will raise ValueError and prevent startup if any preset uses an invalid model
    try:
        validate_presets_or_raise()
        logger.info("Model configuration validated - all presets use verified models")
    except ValueError as e:
        logger.error(f"CRITICAL: {e}")
        raise  # Fail fast - don't start with invalid configuration

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        # Continue anyway - might be using external DB

    yield

    # Shutdown
    logger.info("Shutting down TIMEPOINT Flash")
    await close_db()


# Create FastAPI app
settings = get_settings()

app = FastAPI(
    title="TIMEPOINT Flash",
    description="AI-powered temporal simulation system",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["https://timepoint.ai"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 routes
app.include_router(v1_router)


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Handle HTTP exceptions with consistent response format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "detail": None},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.exception(f"Unexpected error: {exc}")

    if settings.DEBUG:
        detail = str(exc)
    else:
        detail = None

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "detail": detail},
    )


# Health endpoints
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Check application health.

    Returns status of:
    - Application
    - Database connection
    - LLM providers

    Returns:
        HealthResponse with status information.
    """
    # Check database
    db_healthy = await check_db_connection()

    # Check providers (basic check - just if configured)
    providers = {
        "google": bool(settings.GOOGLE_API_KEY),
        "openrouter": bool(settings.OPENROUTER_API_KEY),
    }

    return HealthResponse(
        status="healthy" if db_healthy else "degraded",
        version=__version__,
        database=db_healthy,
        providers=providers,
    )


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """Root endpoint with basic info.

    Returns:
        Basic application information.
    """
    return {
        "name": "TIMEPOINT Flash",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
    }


# API v1 routes placeholder
@app.get("/api/v1/status", tags=["API"])
async def api_status() -> dict[str, Any]:
    """API status endpoint.

    Returns:
        API status and version information.
    """
    return {
        "api_version": "v1",
        "app_version": __version__,
        "environment": settings.ENVIRONMENT.value,
        "primary_provider": settings.PRIMARY_PROVIDER.value,
        "models": settings.get_model_config(),
    }


# Entry point for development
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
