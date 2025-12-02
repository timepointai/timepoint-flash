"""Model discovery API endpoints.

Provides endpoints to discover available LLM models.

Endpoints:
    GET /api/v1/models - List available models
    GET /api/v1/models/{model_id} - Get model details

Examples:
    >>> GET /api/v1/models?capability=text
    >>> {"models": [{"id": "gemini-3-pro-preview", ...}]}

Tests:
    - tests/unit/test_api_models.py::test_list_models
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.config import ProviderType, settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["models"])


# Cache for model list
_model_cache: dict[str, Any] = {}
_cache_expiry: datetime | None = None
CACHE_TTL = timedelta(minutes=15)


# Response Models


class ModelInfo(BaseModel):
    """Information about an LLM model."""

    id: str
    name: str
    provider: str
    capabilities: list[str] = Field(default_factory=list)
    context_length: int | None = None
    pricing: dict[str, float] | None = None
    is_available: bool = True
    is_free: bool = False
    modality: str | None = None  # e.g., "text->text", "text+image->text"


class ModelListResponse(BaseModel):
    """Response containing list of models."""

    models: list[ModelInfo]
    total: int
    cached: bool = False


class ProviderStatus(BaseModel):
    """Status of a provider."""

    provider: str
    available: bool
    models_count: int
    default_text_model: str | None = None
    default_image_model: str | None = None


class ProvidersResponse(BaseModel):
    """Response with provider status."""

    providers: list[ProviderStatus]


# Helper Functions


def get_configured_models() -> list[ModelInfo]:
    """Get list of configured models from settings."""
    models = []

    # Google models
    if settings.GOOGLE_API_KEY:
        models.extend([
            ModelInfo(
                id="gemini-2.5-flash",
                name="Gemini 2.5 Flash",
                provider="google",
                capabilities=["text", "vision"],
                context_length=1000000,
            ),
            ModelInfo(
                id="gemini-3-pro-preview",
                name="Gemini 3 Pro Preview",
                provider="google",
                capabilities=["text", "vision"],
                context_length=2000000,
            ),
            ModelInfo(
                id="imagen-3.0-generate-002",
                name="Imagen 3",
                provider="google",
                capabilities=["image_generation"],
            ),
        ])

    # OpenRouter models (commonly used)
    if settings.OPENROUTER_API_KEY:
        models.extend([
            ModelInfo(
                id="anthropic/claude-3.5-sonnet",
                name="Claude 3.5 Sonnet",
                provider="openrouter",
                capabilities=["text", "vision"],
                context_length=200000,
                pricing={"prompt": 0.000003, "completion": 0.000015},
            ),
            ModelInfo(
                id="openai/gpt-4o",
                name="GPT-4o",
                provider="openrouter",
                capabilities=["text", "vision"],
                context_length=128000,
                pricing={"prompt": 0.000005, "completion": 0.000015},
            ),
            ModelInfo(
                id="google/gemini-3-pro-image-preview",
                name="Nano Banana Pro (Gemini 3 Image)",
                provider="openrouter",
                capabilities=["image_generation"],
                pricing={"prompt": 0.00012, "completion": 0.0},
            ),
        ])

    return models


async def fetch_openrouter_models(free_only: bool = False) -> list[ModelInfo]:
    """Fetch available models from OpenRouter API.

    Returns cached results if within TTL.

    Args:
        free_only: If True, only return free models
    """
    global _model_cache, _cache_expiry

    # Check cache
    cache_key = "openrouter_free" if free_only else "openrouter"
    if _cache_expiry and datetime.now() < _cache_expiry and cache_key in _model_cache:
        return _model_cache[cache_key]

    # Fetch from API
    if not settings.OPENROUTER_API_KEY:
        return []

    try:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
                timeout=15.0,
            )

            if response.status_code == 200:
                data = response.json()
                models = []

                for model_data in data.get("data", []):
                    # Determine capabilities from modality
                    modality = model_data.get("architecture", {}).get("modality", "text->text")
                    capabilities = ["text"]
                    if "image" in modality.lower():
                        capabilities.append("vision")

                    # Check if model is free
                    pricing = model_data.get("pricing", {})
                    prompt_price = float(pricing.get("prompt", "1") or "1")
                    completion_price = float(pricing.get("completion", "1") or "1")
                    is_free = prompt_price == 0 and completion_price == 0

                    # Skip if we only want free models and this isn't free
                    if free_only and not is_free:
                        continue

                    models.append(ModelInfo(
                        id=model_data["id"],
                        name=model_data.get("name", model_data["id"]),
                        provider="openrouter",
                        capabilities=capabilities,
                        context_length=model_data.get("context_length"),
                        pricing={
                            "prompt": prompt_price,
                            "completion": completion_price,
                        },
                        is_free=is_free,
                        modality=modality,
                    ))

                # Update cache
                _model_cache[cache_key] = models
                _cache_expiry = datetime.now() + CACHE_TTL

                return models

    except Exception as e:
        logger.warning(f"Failed to fetch OpenRouter models: {e}")

    return []


def get_best_free_model(models: list[ModelInfo]) -> ModelInfo | None:
    """Get the best free model (by context length as proxy for capability).

    Args:
        models: List of models to choose from

    Returns:
        Best free model or None
    """
    free_models = [m for m in models if m.is_free]
    if not free_models:
        return None
    # Sort by context length (larger = more capable)
    return max(free_models, key=lambda m: m.context_length or 0)


def get_fastest_free_model(models: list[ModelInfo]) -> ModelInfo | None:
    """Get the fastest free model that can still handle structured output.

    For free models, we want speed but also capability.
    Models under 32K context often can't handle structured JSON output.

    Priority:
    1. Gemini Flash free models (best balance of speed + reliable JSON)
    2. Gemini models in general (good structured output)
    3. Claude/Anthropic free models
    4. Other models with :free suffix and >= 32K context

    Args:
        models: List of models to choose from

    Returns:
        Fastest capable free model or None
    """
    free_models = [m for m in models if m.is_free]
    if not free_models:
        return None

    # Minimum context for structured output capability
    MIN_CONTEXT_FOR_STRUCTURED = 32000

    # Filter to capable models first
    capable_models = [
        m for m in free_models
        if (m.context_length or 0) >= MIN_CONTEXT_FOR_STRUCTURED
    ]

    # If no capable models, fall back to all free but prefer larger
    if not capable_models:
        # Return the model with highest context as fallback
        return max(free_models, key=lambda m: m.context_length or 0)

    # Score for speed among capable models
    def speed_score(m: ModelInfo) -> tuple[int, int, int, int, int]:
        # Lower is better
        model_id_lower = m.id.lower()

        # Priority 1: Gemini Flash models (fastest + most reliable JSON)
        is_gemini_flash = 0 if "gemini" in model_id_lower and "flash" in model_id_lower else 1

        # Priority 2: Other Gemini models (good structured output)
        is_gemini = 0 if "gemini" in model_id_lower else 1

        # Priority 3: Claude/Anthropic models (good at following instructions)
        is_claude = 0 if "claude" in model_id_lower or "anthropic" in model_id_lower else 1

        # Priority 4: Dedicated free endpoints (more reliable)
        is_dedicated_free = 0 if ":free" in m.id else 1

        # Priority 5: Smaller context (faster) but already filtered to capable
        ctx = m.context_length or 100000
        return (is_gemini_flash, is_gemini, is_claude, is_dedicated_free, ctx)

    return min(capable_models, key=speed_score)


# Endpoints


class FreeModelsResponse(BaseModel):
    """Response containing free model recommendations."""

    best: ModelInfo | None = Field(None, description="Best free model (highest capability)")
    fastest: ModelInfo | None = Field(None, description="Fastest free model")
    all_free: list[ModelInfo] = Field(default_factory=list, description="All available free models")
    total: int = 0
    note: str = Field(
        default="Free models rotate frequently. Always fetch fresh to get current availability.",
        description="Important note about free model availability"
    )


@router.get("/free", response_model=FreeModelsResponse)
async def get_free_models() -> FreeModelsResponse:
    """Get available free models from OpenRouter.

    Returns the best and fastest free models along with
    the complete list of currently available free models.

    Note: Free models rotate frequently on OpenRouter.
    This endpoint always fetches fresh data.

    Returns:
        FreeModelsResponse with recommended free models
    """
    # Always fetch fresh for free models (they rotate)
    global _model_cache
    if "openrouter_free" in _model_cache:
        del _model_cache["openrouter_free"]

    free_models = await fetch_openrouter_models(free_only=True)

    # Sort by context length for display
    free_models.sort(key=lambda m: m.context_length or 0, reverse=True)

    return FreeModelsResponse(
        best=get_best_free_model(free_models),
        fastest=get_fastest_free_model(free_models),
        all_free=free_models,
        total=len(free_models),
    )


@router.get("", response_model=ModelListResponse)
async def list_models(
    provider: str | None = Query(None, description="Filter by provider (google, openrouter)"),
    capability: str | None = Query(None, description="Filter by capability (text, vision, image_generation)"),
    fetch_remote: bool = Query(False, description="Fetch remote models from OpenRouter"),
    free_only: bool = Query(False, description="Only return free models"),
) -> ModelListResponse:
    """List available LLM models.

    Returns configured models and optionally fetches
    dynamic model list from OpenRouter.

    Args:
        provider: Filter by provider
        capability: Filter by capability
        fetch_remote: Whether to fetch from OpenRouter API
        free_only: Only return free models (requires fetch_remote=true for OpenRouter)

    Returns:
        ModelListResponse with available models
    """
    models = get_configured_models()
    cached = False

    # Optionally fetch remote models
    if fetch_remote:
        remote_models = await fetch_openrouter_models(free_only=free_only)
        cached = bool(_cache_expiry and datetime.now() < _cache_expiry)
        # Merge, avoiding duplicates
        existing_ids = {m.id for m in models}
        for rm in remote_models:
            if rm.id not in existing_ids:
                models.append(rm)

    # Apply free filter to configured models too
    if free_only:
        models = [m for m in models if m.is_free]

    # Apply filters
    if provider:
        models = [m for m in models if m.provider == provider]

    if capability:
        models = [m for m in models if capability in m.capabilities]

    return ModelListResponse(
        models=models,
        total=len(models),
        cached=cached,
    )


@router.get("/providers", response_model=ProvidersResponse)
async def get_providers() -> ProvidersResponse:
    """Get status of configured providers.

    Returns which providers are available and their
    default model assignments.

    Returns:
        ProvidersResponse with provider status
    """
    providers = []

    # Google provider
    google_available = bool(settings.GOOGLE_API_KEY)
    providers.append(ProviderStatus(
        provider="google",
        available=google_available,
        models_count=3 if google_available else 0,
        default_text_model=settings.JUDGE_MODEL if google_available else None,
        default_image_model="imagen-3.0-generate-002" if google_available else None,
    ))

    # OpenRouter provider
    openrouter_available = bool(settings.OPENROUTER_API_KEY)
    providers.append(ProviderStatus(
        provider="openrouter",
        available=openrouter_available,
        models_count=300 if openrouter_available else 0,  # Approximate
        default_text_model="anthropic/claude-3.5-sonnet" if openrouter_available else None,
        default_image_model=settings.IMAGE_MODEL if openrouter_available else None,
    ))

    return ProvidersResponse(providers=providers)


@router.get("/{model_id:path}")
async def get_model_info(model_id: str) -> ModelInfo:
    """Get detailed information about a specific model.

    Args:
        model_id: The model identifier (e.g., 'gemini-3-pro-preview')

    Returns:
        ModelInfo with model details

    Raises:
        HTTPException: If model not found
    """
    from fastapi import HTTPException

    # Check configured models
    models = get_configured_models()
    for model in models:
        if model.id == model_id:
            return model

    # Check cached OpenRouter models
    if "openrouter" in _model_cache:
        for model in _model_cache["openrouter"]:
            if model.id == model_id:
                return model

    raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
