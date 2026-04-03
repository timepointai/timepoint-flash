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

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from app import __version__
from app.api.v1 import router as v1_router
from app.config import get_settings, validate_presets_or_raise
from app.core.request_context import set_request_id
from app.database import check_db_connection, close_db, init_db
from app.feature_flags import init_posthog, shutdown_posthog

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

    # Initialize PostHog for feature flags and analytics
    init_posthog()

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

    # Initialize blob storage if enabled
    _settings = get_settings()
    if _settings.BLOB_STORAGE_ENABLED:
        from pathlib import Path

        storage_root = Path(_settings.BLOB_STORAGE_ROOT)
        try:
            storage_root.mkdir(parents=True, exist_ok=True)
            logger.info(f"Blob storage initialized: {storage_root.resolve()}")
        except Exception as e:
            logger.error(f"Blob storage initialization failed: {e}")

    # Initialize OpenRouter model registry for dynamic fallback selection
    if _settings.OPENROUTER_API_KEY:
        from app.core.model_registry import OpenRouterModelRegistry

        registry = OpenRouterModelRegistry.get_instance()
        await registry.initialize(api_key=_settings.OPENROUTER_API_KEY)
        registry.start_background_refresh(interval=3600)

    yield

    # Shutdown
    logger.info("Shutting down TIMEPOINT Flash")

    # Stop model registry background refresh
    try:
        from app.core.model_registry import OpenRouterModelRegistry

        OpenRouterModelRegistry.get_instance().stop_background_refresh()
    except Exception:
        pass

    await close_db()
    shutdown_posthog()


_CORRELATION_HEADER = "X-Request-ID"


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Propagate X-Request-ID from Gateway into the async request context.

    Reads the X-Request-ID header forwarded by the API Gateway and stores it
    in a Python contextvar so that LLM call logging can include the correlation
    ID without threading it explicitly through every function signature.

    The header is also echoed back in the response so clients can correlate
    their request with logs across all services.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(_CORRELATION_HEADER)
        set_request_id(request_id)
        request.state.request_id = request_id
        response = await call_next(request)
        if request_id:
            response.headers[_CORRELATION_HEADER] = request_id
        return response


# Service key middleware — gate all traffic when FLASH_SERVICE_KEY is set
_OPEN_PATHS = {"/health", "/health/deep", "/", "/docs", "/redoc", "/openapi.json"}


class ServiceKeyMiddleware(BaseHTTPMiddleware):
    """Reject requests without a valid X-Service-Key header.

    When FLASH_SERVICE_KEY is empty, all requests are allowed (open access).
    Health/docs endpoints are always exempt.
    """

    async def dispatch(self, request: Request, call_next):
        service_key = get_settings().FLASH_SERVICE_KEY
        if service_key and request.url.path not in _OPEN_PATHS:
            provided = request.headers.get("X-Service-Key", "")
            if provided != service_key:
                return JSONResponse(
                    status_code=403,
                    content={"error": "Invalid or missing service key"},
                )
        return await call_next(request)


# Create FastAPI app
settings = get_settings()

app = FastAPI(
    title="TIMEPOINT Flash",
    description="AI-powered temporal simulation system",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json",  # Always available for client code generation
)

# Service key middleware (outermost — runs before CORS)
if settings.FLASH_SERVICE_KEY:
    app.add_middleware(ServiceKeyMiddleware)

# Correlation ID middleware — propagate X-Request-ID from Gateway
app.add_middleware(CorrelationIDMiddleware)

# CORS middleware (only when browser callers are expected)
if settings.CORS_ENABLED:
    _cors_origins: list[str] = ["*"] if settings.DEBUG else ["https://timepoint.ai"]
    if settings.CORS_ORIGINS:
        _cors_origins.extend(
            origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
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
@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Instant liveness probe -- no I/O."""
    return {
        "status": "healthy",
        "version": __version__,
        "database": True,
        "providers": {
            "google": bool(settings.GOOGLE_API_KEY),
            "openrouter": bool(settings.OPENROUTER_API_KEY),
        },
    }


@app.get("/health/deep", response_model=HealthResponse, tags=["Health"])
async def health_deep() -> HealthResponse:
    """Deep health check -- verifies DB and provider connectivity."""
    try:
        db_healthy = await asyncio.wait_for(check_db_connection(), timeout=5)
    except TimeoutError:
        logging.getLogger(__name__).error("Health deep: database connection timed out after 5s")
        db_healthy = False

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
