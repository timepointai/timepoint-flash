"""Dynamic OpenRouter model registry with caching.

Fetches available models from OpenRouter's /api/v1/models endpoint at startup,
caches them, and provides dynamic model selection for fallback chains.

The registry is advisory — if OpenRouter is unreachable, every code path
falls back to existing hardcoded defaults. No existing behavior breaks.
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from app.config import ProviderType

logger = logging.getLogger(__name__)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
# Google Gen AI (Gemini Developer API) catalog endpoint. Returns models named
# like ``models/gemini-2.5-flash``; we normalise the ``models/`` prefix away so
# membership matches the bare slugs in VerifiedModels.GOOGLE_TEXT.
GOOGLE_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_FETCH_TIMEOUT = 5.0  # seconds

# Hardcoded defaults — used when registry has no data
_DEFAULT_TEXT_FALLBACK = "google/gemini-2.0-flash-001"
_DEFAULT_IMAGE_FALLBACK = "google/gemini-2.5-flash-image-preview"


class OpenRouterModelRegistry:
    """Singleton that caches OpenRouter model data for dynamic fallback selection."""

    _instance: "OpenRouterModelRegistry | None" = None

    def __init__(self) -> None:
        self._models: dict[str, dict[str, Any]] = {}
        self._google_models: set[str] = set()
        self._last_refresh: float = 0.0
        self._google_last_refresh: float = 0.0
        self._api_key: str | None = None
        self._google_api_key: str | None = None
        self._refresh_task: asyncio.Task | None = None

    @classmethod
    def get_instance(cls) -> "OpenRouterModelRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        if cls._instance is not None:
            cls._instance.stop_background_refresh()
        cls._instance = None

    async def initialize(self, api_key: str) -> None:
        """Fetch models on startup. Non-blocking, gracefully handles failure."""
        self._api_key = api_key
        success = await self.refresh()
        if success:
            logger.info(
                "OpenRouter model registry initialized: %d models cached",
                len(self._models),
            )
        else:
            logger.warning("OpenRouter model registry: API unreachable, using hardcoded defaults")

    async def refresh(self) -> bool:
        """Fetch model list from OpenRouter and update cache.

        Returns:
            True if fetch succeeded, False otherwise.
        """
        if not self._api_key:
            return False

        try:
            async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
                resp = await client.get(
                    OPENROUTER_MODELS_URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                if resp.status_code != 200:
                    logger.warning("OpenRouter models API returned %d", resp.status_code)
                    return False

                data = resp.json()
                models_list = data.get("data", [])
                new_cache: dict[str, dict[str, Any]] = {}
                for m in models_list:
                    model_id = m.get("id")
                    if model_id:
                        new_cache[model_id] = m

                self._models = new_cache
                self._last_refresh = time.monotonic()
                return True

        except Exception as e:
            logger.warning("OpenRouter model registry refresh failed: %s", e)
            return False

    def start_background_refresh(self, interval: int = 3600) -> None:
        """Start hourly background refresh task."""
        if self._refresh_task is not None:
            return  # Already running

        async def _loop() -> None:
            while True:
                await asyncio.sleep(interval)
                try:
                    await self.refresh()
                except Exception:
                    pass  # B110: intentional — refresh is best-effort

        self._refresh_task = asyncio.create_task(_loop())

    def stop_background_refresh(self) -> None:
        """Cancel background refresh task."""
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            self._refresh_task = None

    def is_model_available(self, model_id: str) -> bool:
        """Check if a model is in the cached OpenRouter list."""
        return model_id in self._models

    @property
    def model_count(self) -> int:
        return len(self._models)

    # ------------------------------------------------------------------
    # Google-native catalog (liveness guard)
    # ------------------------------------------------------------------
    async def refresh_google(self, api_key: str | None = None) -> bool:
        """Fetch the Google Gen AI model catalog and cache the bare slugs.

        The Gemini Developer API lists models under names like
        ``models/gemini-2.5-flash``; we strip the ``models/`` prefix so a
        membership check against ``VerifiedModels.GOOGLE_TEXT`` (which holds
        bare slugs like ``gemini-2.5-flash``) works.

        One bounded fetch — cached for the life of the process. Returns True
        on success, False on any failure (so callers can fail soft).
        """
        key = api_key or self._google_api_key
        if key:
            self._google_api_key = key
        if not key:
            return False
        try:
            async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
                resp = await client.get(
                    GOOGLE_MODELS_URL,
                    params={"key": key, "pageSize": 1000},
                )
                if resp.status_code != 200:
                    logger.warning("Google models API returned %d", resp.status_code)
                    return False
                data = resp.json()
                new_cache: set[str] = set()
                for m in data.get("models", []):
                    name = m.get("name") or m.get("baseModelId") or ""
                    if name.startswith("models/"):
                        name = name[len("models/") :]
                    if name:
                        new_cache.add(name)
                self._google_models = new_cache
                self._google_last_refresh = time.monotonic()
                return True
        except Exception as e:  # noqa: BLE001 — best-effort catalog fetch
            logger.warning("Google model registry refresh failed: %s", e)
            return False

    @property
    def google_model_count(self) -> int:
        return len(self._google_models)

    def is_google_model_available(self, model_id: str) -> bool:
        """Check if a bare Google slug is present in the cached Google catalog."""
        return model_id in self._google_models

    def has_catalog(self, provider: "ProviderType") -> bool:
        """Whether a live catalog has been loaded for ``provider``.

        Liveness can only be *asserted* when a catalog is present. With no
        catalog (offline / no key / unreachable), callers must fail soft —
        we cannot claim a slug is dead just because we never fetched a list.
        """
        from app.config import ProviderType

        if provider == ProviderType.GOOGLE:
            return bool(self._google_models)
        if provider == ProviderType.OPENROUTER:
            return bool(self._models)
        return False

    def is_slug_live(self, model_id: str, provider: "ProviderType") -> bool:
        """Liveness check: is ``model_id`` present in the live catalog for ``provider``?

        IMPORTANT: only meaningful when :meth:`has_catalog` is True for that
        provider. When no catalog is loaded this returns False — callers should
        gate on ``has_catalog`` first and fail soft (not fail-closed) on a
        missing catalog, but fail loud on a *dead* slug when a catalog exists.
        """
        from app.config import ProviderType

        if provider == ProviderType.GOOGLE:
            return model_id in self._google_models
        if provider == ProviderType.OPENROUTER:
            return model_id in self._models
        # No live catalog for STABILITY here.
        return False

    def get_best_text_model(self, prefer_free: bool = False) -> str | None:
        """Find the best available text model.

        Heuristic: filter to google/gemini* models, exclude :free by default,
        sort by context_length descending.

        Returns:
            Model ID or None if cache is empty.
        """
        if not self._models:
            return None

        candidates = []
        for model_id, info in self._models.items():
            if not model_id.startswith("google/gemini"):
                continue
            if not prefer_free and model_id.endswith(":free"):
                continue
            if prefer_free and not model_id.endswith(":free"):
                continue

            # Filter to text-capable models (no "image" in output_modalities)
            arch = info.get("architecture") or {}
            output_mods = arch.get("output_modalities") or []
            # Accept models that produce text
            if isinstance(output_mods, list) and "text" not in output_mods:
                continue

            ctx = info.get("context_length", 0)
            candidates.append((model_id, ctx))

        if not candidates:
            return None

        # Sort by context_length descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def get_best_image_model(self, permissive_only: bool = False) -> str | None:
        """Find the best available image generation model.

        Heuristic: filter to models with "image" in output_modalities,
        prefer gemini models (unless permissive_only is set).

        Args:
            permissive_only: If True, only return open-weight models
                (no Google, OpenAI, Anthropic).

        Returns:
            Model ID or None if cache is empty.
        """
        from app.core.model_policy import is_model_permissive

        if not self._models:
            return None

        gemini_candidates = []
        other_candidates = []

        for model_id, info in self._models.items():
            arch = info.get("architecture") or {}
            output_mods = arch.get("output_modalities") or []
            if not isinstance(output_mods, list) or "image" not in output_mods:
                continue

            if permissive_only and not is_model_permissive(model_id):
                continue

            ctx = info.get("context_length", 0)
            if "gemini" in model_id.lower():
                gemini_candidates.append((model_id, ctx))
            else:
                other_candidates.append((model_id, ctx))

        if not permissive_only:
            # Prefer gemini models, sorted by context_length desc
            if gemini_candidates:
                gemini_candidates.sort(key=lambda x: x[1], reverse=True)
                return gemini_candidates[0][0]

        if other_candidates:
            other_candidates.sort(key=lambda x: x[1], reverse=True)
            return other_candidates[0][0]

        # Fallback: if permissive_only but no permissive image models found,
        # return gemini via OpenRouter (still better than nothing)
        if gemini_candidates:
            gemini_candidates.sort(key=lambda x: x[1], reverse=True)
            return gemini_candidates[0][0]

        return None
