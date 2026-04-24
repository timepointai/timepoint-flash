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


# Edge auth middleware — gate all non-health traffic (API-4)
_OPEN_PATHS = {"/health", "/health/deep", "/", "/docs", "/redoc", "/openapi.json"}


class GatewayAuthMiddleware(BaseHTTPMiddleware):
    """Authenticate inbound traffic at the edge (API-4).

    Two accepted request shapes:

    1. **Signed gateway request** — carries a valid ``X-Gateway-Signature`` /
       ``X-Gateway-Timestamp`` HMAC'd with ``GATEWAY_SIGNING_SECRET``. The
       signature binds ``X-User-Id`` to the request, proving it was minted by
       the Gateway (not an attacker with a leaked shared secret). These
       requests are flagged ``request.state.gateway_verified = True`` so that
       downstream dependencies can trust ``X-User-Id``.

    2. **Legacy system call** — carries only a valid ``X-Service-Key`` matching
       ``FLASH_SERVICE_KEY``. Permitted while ``ALLOW_LEGACY_SERVICE_KEY`` is
       True, but these calls are treated as unauthenticated system traffic and
       may NOT impersonate users (``get_current_user`` returns None for them).

    Everything else is rejected:

    * When ``REQUIRE_SIGNED_GATEWAY=True`` (production target), any
      non-health request without a valid signature returns 403.
    * When ``FLASH_SERVICE_KEY`` is set and no valid key/signature is
      presented, the request is rejected 403.
    * ``/health``, ``/health/deep``, ``/``, ``/docs``, ``/redoc``,
      ``/openapi.json`` are always open.
    """

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        path = request.url.path

        # Always allow health/docs/root — these must be reachable for Railway
        # health checks and OpenAPI discovery.
        if path in _OPEN_PATHS:
            request.state.gateway_verified = False
            return await call_next(request)

        # Try gateway HMAC verification first — this is the strong path.
        from app.auth.gateway_signing import (
            SIGNATURE_HEADER,
            TIMESTAMP_HEADER,
            verify_gateway_signature,
        )

        signature = request.headers.get(SIGNATURE_HEADER, "")
        timestamp = request.headers.get(TIMESTAMP_HEADER, "")
        user_id = request.headers.get("X-User-Id") or request.headers.get("X-User-ID") or ""

        gateway_verified = False
        if signature and timestamp and settings.GATEWAY_SIGNING_SECRET:
            gateway_verified = verify_gateway_signature(
                secret=settings.GATEWAY_SIGNING_SECRET,
                method=request.method,
                path=path,
                user_id=user_id,
                timestamp_header=timestamp,
                signature_header=signature,
            )
            if not gateway_verified:
                # A signature was presented but failed verification. Reject —
                # don't silently fall through to legacy auth.
                logger.warning(
                    "Rejected request with invalid gateway signature: %s %s",
                    request.method,
                    path,
                )
                return JSONResponse(
                    status_code=403,
                    content={"error": "Invalid gateway signature"},
                )

        request.state.gateway_verified = gateway_verified

        if gateway_verified:
            return await call_next(request)

        # No valid gateway signature. Fall back to legacy X-Service-Key path
        # if configured.
        if settings.FLASH_SERVICE_KEY:
            provided = request.headers.get("X-Service-Key", "")
            legacy_key_ok = provided == settings.FLASH_SERVICE_KEY

            if settings.REQUIRE_SIGNED_GATEWAY:
                # Strict mode: legacy key is not enough — must be signed.
                logger.warning(
                    "Rejected unsigned request (REQUIRE_SIGNED_GATEWAY=True): %s %s",
                    request.method,
                    path,
                )
                return JSONResponse(
                    status_code=403,
                    content={"error": "Gateway signature required"},
                )

            if legacy_key_ok and settings.ALLOW_LEGACY_SERVICE_KEY:
                # System call path — allowed through but not user-authenticated.
                return await call_next(request)

            return JSONResponse(
                status_code=403,
                content={"error": "Invalid or missing service key"},
            )

        # No FLASH_SERVICE_KEY configured — open access mode (dev only).
        return await call_next(request)


# Backwards-compat alias — a few external imports may still reference the
# old name. Kept so downstream code does not break during the rollout.
ServiceKeyMiddleware = GatewayAuthMiddleware


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

# Gateway auth middleware (outermost — runs before CORS).
# Always installed so we enforce consistently whenever any edge-auth knob is
# configured. When both FLASH_SERVICE_KEY and GATEWAY_SIGNING_SECRET are empty
# the middleware falls through to open-access mode (dev/local).
if settings.FLASH_SERVICE_KEY or settings.GATEWAY_SIGNING_SECRET:
    app.add_middleware(GatewayAuthMiddleware)

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
