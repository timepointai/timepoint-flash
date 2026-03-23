"""Dynamic OpenRouter model registry with caching.

Fetches available models from OpenRouter's /api/v1/models endpoint at startup,
caches them, and provides dynamic model selection for fallback chains.

The registry is advisory — if OpenRouter is unreachable, every code path
falls back to existing hardcoded defaults. No existing behavior breaks.
"""

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_FETCH_TIMEOUT = 5.0  # seconds

# Hardcoded defaults — used when registry has no data
_DEFAULT_TEXT_FALLBACK = "google/gemini-2.0-flash-001"
_DEFAULT_IMAGE_FALLBACK = "google/gemini-2.5-flash-image-preview"


class OpenRouterModelRegistry:
    """Singleton that caches OpenRouter model data for dynamic fallback selection."""

    _instance: "OpenRouterModelRegistry | None" = None

    def __init__(self) -> None:
        self._models: dict[str, dict[str, Any]] = {}
        self._last_refresh: float = 0.0
        self._api_key: str | None = None
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
        """Check if a model is in the cached list."""
        return model_id in self._models

    @property
    def model_count(self) -> int:
        return len(self._models)

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
