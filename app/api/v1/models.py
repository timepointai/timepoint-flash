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


async def fetch_openrouter_models() -> list[ModelInfo]:
    """Fetch available models from OpenRouter API.

    Returns cached results if within TTL.
    """
    global _model_cache, _cache_expiry

    # Check cache
    if _cache_expiry and datetime.now() < _cache_expiry and "openrouter" in _model_cache:
        return _model_cache["openrouter"]

    # Fetch from API
    if not settings.OPENROUTER_API_KEY:
        return []

    try:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                models = []

                for model_data in data.get("data", [])[:50]:  # Limit to 50 models
                    # Determine capabilities from modality
                    modality = model_data.get("architecture", {}).get("modality", "text->text")
                    capabilities = ["text"]
                    if "image" in modality:
                        capabilities.append("vision")

                    models.append(ModelInfo(
                        id=model_data["id"],
                        name=model_data.get("name", model_data["id"]),
                        provider="openrouter",
                        capabilities=capabilities,
                        context_length=model_data.get("context_length"),
                        pricing={
                            "prompt": float(model_data.get("pricing", {}).get("prompt", 0)),
                            "completion": float(model_data.get("pricing", {}).get("completion", 0)),
                        },
                    ))

                # Update cache
                _model_cache["openrouter"] = models
                _cache_expiry = datetime.now() + CACHE_TTL

                return models

    except Exception as e:
        logger.warning(f"Failed to fetch OpenRouter models: {e}")

    return []


# Endpoints


@router.get("", response_model=ModelListResponse)
async def list_models(
    provider: str | None = Query(None, description="Filter by provider (google, openrouter)"),
    capability: str | None = Query(None, description="Filter by capability (text, vision, image_generation)"),
    fetch_remote: bool = Query(False, description="Fetch remote models from OpenRouter"),
) -> ModelListResponse:
    """List available LLM models.

    Returns configured models and optionally fetches
    dynamic model list from OpenRouter.

    Args:
        provider: Filter by provider
        capability: Filter by capability
        fetch_remote: Whether to fetch from OpenRouter API

    Returns:
        ModelListResponse with available models
    """
    models = get_configured_models()
    cached = False

    # Optionally fetch remote models
    if fetch_remote:
        remote_models = await fetch_openrouter_models()
        cached = bool(_cache_expiry and datetime.now() < _cache_expiry)
        # Merge, avoiding duplicates
        existing_ids = {m.id for m in models}
        for rm in remote_models:
            if rm.id not in existing_ids:
                models.append(rm)

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
