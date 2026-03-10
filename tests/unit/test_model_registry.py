"""Unit tests for OpenRouter model registry.

All tests use mocked HTTP responses — no real API calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.model_registry import OpenRouterModelRegistry

# Sample API response data
SAMPLE_MODELS_RESPONSE = {
    "data": [
        {
            "id": "google/gemini-2.0-flash-001",
            "name": "Gemini 2.0 Flash",
            "context_length": 1000000,
            "pricing": {"prompt": "0", "completion": "0"},
            "architecture": {
                "output_modalities": ["text"],
            },
        },
        {
            "id": "google/gemini-2.0-flash-001:free",
            "name": "Gemini 2.0 Flash (free)",
            "context_length": 1000000,
            "pricing": {"prompt": "0", "completion": "0"},
            "architecture": {
                "output_modalities": ["text"],
            },
        },
        {
            "id": "google/gemini-2.5-flash-image-preview",
            "name": "Gemini 2.5 Flash Image Preview",
            "context_length": 500000,
            "pricing": {"prompt": "0", "completion": "0"},
            "architecture": {
                "output_modalities": ["text", "image"],
            },
        },
        {
            "id": "google/gemini-3-flash-preview",
            "name": "Gemini 3 Flash Preview",
            "context_length": 2000000,
            "pricing": {"prompt": "0", "completion": "0"},
            "architecture": {
                "output_modalities": ["text"],
            },
        },
        {
            "id": "anthropic/claude-3.5-sonnet",
            "name": "Claude 3.5 Sonnet",
            "context_length": 200000,
            "pricing": {"prompt": "3", "completion": "15"},
            "architecture": {
                "output_modalities": ["text"],
            },
        },
        {
            "id": "black-forest-labs/flux-schnell",
            "name": "FLUX Schnell",
            "context_length": 0,
            "pricing": {"prompt": "0", "completion": "0"},
            "architecture": {
                "output_modalities": ["image"],
            },
        },
    ]
}


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the singleton before each test."""
    OpenRouterModelRegistry.reset()
    yield
    OpenRouterModelRegistry.reset()


@pytest.mark.fast
class TestRegistrySingleton:
    def test_singleton_pattern(self):
        r1 = OpenRouterModelRegistry.get_instance()
        r2 = OpenRouterModelRegistry.get_instance()
        assert r1 is r2

    def test_reset(self):
        r1 = OpenRouterModelRegistry.get_instance()
        OpenRouterModelRegistry.reset()
        r2 = OpenRouterModelRegistry.get_instance()
        assert r1 is not r2


@pytest.mark.fast
class TestRegistryInitialization:
    @pytest.mark.asyncio
    async def test_initialization_success(self):
        registry = OpenRouterModelRegistry.get_instance()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_MODELS_RESPONSE

        with patch("app.core.model_registry.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await registry.initialize(api_key="test-key")

        assert registry.model_count == 6
        assert registry.is_model_available("google/gemini-2.0-flash-001")

    @pytest.mark.asyncio
    async def test_initialization_failure_graceful(self):
        registry = OpenRouterModelRegistry.get_instance()

        with patch("app.core.model_registry.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await registry.initialize(api_key="test-key")

        # Should not raise, cache stays empty
        assert registry.model_count == 0

    @pytest.mark.asyncio
    async def test_initialization_non_200(self):
        registry = OpenRouterModelRegistry.get_instance()

        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("app.core.model_registry.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await registry.initialize(api_key="test-key")

        assert registry.model_count == 0


@pytest.mark.fast
class TestModelAvailability:
    def _populate_registry(self, registry: OpenRouterModelRegistry):
        """Directly populate cache for testing without HTTP calls."""
        for m in SAMPLE_MODELS_RESPONSE["data"]:
            registry._models[m["id"]] = m

    def test_is_model_available(self):
        registry = OpenRouterModelRegistry.get_instance()
        self._populate_registry(registry)

        assert registry.is_model_available("google/gemini-2.0-flash-001")
        assert registry.is_model_available("anthropic/claude-3.5-sonnet")
        assert not registry.is_model_available("nonexistent/model")

    def test_is_model_available_empty_cache(self):
        registry = OpenRouterModelRegistry.get_instance()
        assert not registry.is_model_available("google/gemini-2.0-flash-001")


@pytest.mark.fast
class TestModelSelection:
    def _populate_registry(self, registry: OpenRouterModelRegistry):
        for m in SAMPLE_MODELS_RESPONSE["data"]:
            registry._models[m["id"]] = m

    def test_get_best_text_model(self):
        registry = OpenRouterModelRegistry.get_instance()
        self._populate_registry(registry)

        best = registry.get_best_text_model()
        assert best is not None
        assert best.startswith("google/gemini")
        # Should not be a :free model
        assert not best.endswith(":free")
        # Should be the one with highest context_length
        assert best == "google/gemini-3-flash-preview"

    def test_get_best_text_model_prefer_free(self):
        registry = OpenRouterModelRegistry.get_instance()
        self._populate_registry(registry)

        best = registry.get_best_text_model(prefer_free=True)
        assert best is not None
        assert best.endswith(":free")

    def test_get_best_image_model(self):
        registry = OpenRouterModelRegistry.get_instance()
        self._populate_registry(registry)

        best = registry.get_best_image_model()
        assert best is not None
        # Should prefer gemini model over flux
        assert "gemini" in best

    def test_fallback_when_cache_empty(self):
        registry = OpenRouterModelRegistry.get_instance()

        assert registry.get_best_text_model() is None
        assert registry.get_best_image_model() is None


@pytest.mark.fast
class TestBackgroundRefresh:
    def test_stop_background_refresh_no_task(self):
        """Stopping when no task is running should not raise."""
        registry = OpenRouterModelRegistry.get_instance()
        registry.stop_background_refresh()  # should be a no-op

    @pytest.mark.asyncio
    async def test_refresh_without_api_key(self):
        """Refresh without setting api_key returns False."""
        registry = OpenRouterModelRegistry.get_instance()
        result = await registry.refresh()
        assert result is False
