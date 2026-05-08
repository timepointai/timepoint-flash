"""Unit tests for OpenRouter native routing: models[], provider.order, Retry-After.

Tests the server-side failover parameters injected into chat/completions requests
and the Retry-After sleep-and-retry logic added on top of the multi-key iterator.

Coverage matrix:
    Config:
        - openrouter_models: env var parsed, default fallback chain returned
        - openrouter_provider_order: env var parsed, default provider order returned
    Request body:
        - models[] injected when _models is non-empty
        - provider object injected (order, allow_fallbacks, require_parameters)
        - require_parameters=True forwarded to payload
        - provider block absent when _models and _provider_order both empty
    Retry-After:
        - 429 with Retry-After header → sleep min(header, 30), retry once
        - 503 with Retry-After header → sleep min(header, 30), retry once
        - 429 without Retry-After header → no sleep, rotate key immediately
        - Retry-After > 30 → capped at 30 seconds
        - No double-retry: if sleep-and-retry also fails, key is skipped (not retried again)
        - 401 / 402 / 400 → no Retry-After sleep, existing key-rotation / error behavior

Run with:
    pytest tests/unit/test_openrouter_native_routing.py -v
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.providers.base import ProviderError
from app.core.providers.openrouter import OpenRouterProvider

# ---------------------------------------------------------------------------
# Helpers (mirrors test_openrouter_multikey.py pattern)
# ---------------------------------------------------------------------------


def _chat_response(content: str = "ok") -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {"content": content, "role": "assistant"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3},
    }


def _error_response(status: int, message: str = "error") -> dict[str, Any]:
    return {"error": {"message": message, "code": status}}


def _make_response(
    status: int,
    body: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    return httpx.Response(
        status_code=status,
        headers=h,
        content=json.dumps(body).encode(),
    )


class _CapturingTransport(httpx.AsyncBaseTransport):
    """Records every request and returns a fixed 200 success response."""

    def __init__(self, response_body: dict[str, Any] | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self._body = response_body or _chat_response()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return _make_response(200, self._body)


class _SequenceTransport(httpx.AsyncBaseTransport):
    """Return a fixed sequence of responses."""

    def __init__(self, responses: list[httpx.Response]) -> None:
        self._iter = iter(responses)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        try:
            return next(self._iter)
        except StopIteration:
            pytest.fail(f"Unexpected extra request to {request.url}")


def _make_provider(
    keys: list[str] = ("sk-test",),
    models: list[str] | None = None,
    provider_order: list[str] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> OpenRouterProvider:
    provider = OpenRouterProvider(
        api_keys=list(keys),
        models=models,
        provider_order=provider_order,
        base_url="https://openrouter.ai/api/v1",
    )
    t = transport or _CapturingTransport()
    provider._client = httpx.AsyncClient(
        base_url="https://openrouter.ai/api/v1",
        transport=t,
        headers={
            "HTTP-Referer": "https://timepoint.ai",
            "X-Title": "TIMEPOINT Flash",
            "Content-Type": "application/json",
        },
    )
    return provider


# ---------------------------------------------------------------------------
# Config — openrouter_models and openrouter_provider_order properties
# ---------------------------------------------------------------------------


@pytest.mark.fast
class TestConfigOpenrouterNativeRouting:
    """Test Settings.openrouter_models and openrouter_provider_order parsing."""

    def test_openrouter_models_default(self):
        from app.config import Settings

        s = Settings(OPENROUTER_MODELS=None)
        models = s.openrouter_models
        assert isinstance(models, list)
        assert len(models) == 3
        # All must be slash-delimited OpenRouter model IDs
        assert all("/" in m for m in models)

    def test_openrouter_models_env_parsed(self):
        from app.config import Settings

        s = Settings(OPENROUTER_MODELS="anthropic/claude-3.5-haiku,openai/gpt-4o-mini")
        assert s.openrouter_models == ["anthropic/claude-3.5-haiku", "openai/gpt-4o-mini"]

    def test_openrouter_models_strips_whitespace(self):
        from app.config import Settings

        s = Settings(OPENROUTER_MODELS=" anthropic/claude-3.5-haiku , openai/gpt-4o-mini ")
        assert s.openrouter_models == ["anthropic/claude-3.5-haiku", "openai/gpt-4o-mini"]

    def test_openrouter_models_ignores_empty_segments(self):
        from app.config import Settings

        s = Settings(OPENROUTER_MODELS="model-a,,  ,model-b")
        assert s.openrouter_models == ["model-a", "model-b"]

    def test_openrouter_provider_order_default(self):
        from app.config import Settings

        s = Settings(OPENROUTER_PROVIDER_ORDER=None)
        order = s.openrouter_provider_order
        assert isinstance(order, list)
        assert len(order) == 3

    def test_openrouter_provider_order_env_parsed(self):
        from app.config import Settings

        s = Settings(OPENROUTER_PROVIDER_ORDER="Anthropic,OpenAI,Together")
        assert s.openrouter_provider_order == ["Anthropic", "OpenAI", "Together"]

    def test_openrouter_provider_order_strips_whitespace(self):
        from app.config import Settings

        s = Settings(OPENROUTER_PROVIDER_ORDER=" Google AI Studio , Together ")
        assert s.openrouter_provider_order == ["Google AI Studio", "Together"]


# ---------------------------------------------------------------------------
# Provider init — models and provider_order constructor params
# ---------------------------------------------------------------------------


@pytest.mark.fast
class TestOpenRouterProviderNativeRoutingInit:
    """Test that models / provider_order constructor params are stored."""

    def test_models_stored(self):
        p = OpenRouterProvider(
            api_key="sk-x",
            models=["m1", "m2"],
        )
        assert p._models == ["m1", "m2"]

    def test_provider_order_stored(self):
        p = OpenRouterProvider(
            api_key="sk-x",
            provider_order=["Google AI Studio", "Together"],
        )
        assert p._provider_order == ["Google AI Studio", "Together"]

    def test_defaults_empty_lists(self):
        p = OpenRouterProvider(api_key="sk-x")
        assert p._models == []
        assert p._provider_order == []

    def test_none_becomes_empty_list(self):
        p = OpenRouterProvider(api_key="sk-x", models=None, provider_order=None)
        assert p._models == []
        assert p._provider_order == []


# ---------------------------------------------------------------------------
# Request body — models[] and provider object injected
# ---------------------------------------------------------------------------


@pytest.mark.fast
@pytest.mark.asyncio
class TestNativeRoutingPayload:
    """Verify models[] and provider block are injected into the request body."""

    async def test_models_injected_in_body(self):
        """When _models is set, 'models' key appears in request JSON."""
        transport = _CapturingTransport()
        provider = _make_provider(
            models=["fallback/model-a", "fallback/model-b"],
            transport=transport,
        )
        await provider.call_text(prompt="hello", model="primary/model")
        assert len(transport.requests) == 1
        body = json.loads(transport.requests[0].content)
        assert body["models"] == ["fallback/model-a", "fallback/model-b"]

    async def test_provider_object_injected_in_body(self):
        """When _models is set, 'provider' block appears in request JSON."""
        transport = _CapturingTransport()
        provider = _make_provider(
            models=["fallback/model-a"],
            provider_order=["Google AI Studio", "Together"],
            transport=transport,
        )
        await provider.call_text(prompt="hello", model="primary/model")
        body = json.loads(transport.requests[0].content)
        assert "provider" in body
        prov = body["provider"]
        assert prov["order"] == ["Google AI Studio", "Together"]
        assert prov["allow_fallbacks"] is True

    async def test_require_parameters_forwarded(self):
        """require_parameters=True is always set when provider block is present."""
        transport = _CapturingTransport()
        provider = _make_provider(
            models=["fallback/model"],
            provider_order=["Fireworks"],
            transport=transport,
        )
        await provider.call_text(prompt="hello", model="primary/model")
        body = json.loads(transport.requests[0].content)
        assert body["provider"]["require_parameters"] is True

    async def test_no_provider_block_when_empty(self):
        """When _models and _provider_order are both empty, no provider block is added."""
        transport = _CapturingTransport()
        provider = _make_provider(models=[], provider_order=[], transport=transport)
        await provider.call_text(prompt="hello", model="primary/model")
        body = json.loads(transport.requests[0].content)
        assert "models" not in body
        assert "provider" not in body

    async def test_provider_block_present_with_only_provider_order(self):
        """provider block is injected when only provider_order is set (no models)."""
        transport = _CapturingTransport()
        provider = _make_provider(
            models=[],
            provider_order=["Anthropic"],
            transport=transport,
        )
        await provider.call_text(prompt="hello", model="primary/model")
        body = json.loads(transport.requests[0].content)
        assert "provider" in body
        assert body["provider"]["order"] == ["Anthropic"]
        assert "models" not in body

    async def test_primary_model_field_unchanged(self):
        """The primary 'model' field is preserved alongside models[]."""
        transport = _CapturingTransport()
        provider = _make_provider(
            models=["fallback/model"],
            transport=transport,
        )
        await provider.call_text(prompt="hello", model="primary/exact")
        body = json.loads(transport.requests[0].content)
        assert body["model"] == "primary/exact"
        assert "fallback/model" in body["models"]


# ---------------------------------------------------------------------------
# Retry-After handling
# ---------------------------------------------------------------------------


@pytest.mark.fast
@pytest.mark.asyncio
class TestRetryAfter:
    """Verify Retry-After header is honoured on 429 and 503."""

    async def test_429_with_retry_after_sleeps_and_retries(self):
        """On 429 + Retry-After, provider sleeps and retries same key."""
        transport = _SequenceTransport(
            [
                _make_response(429, _error_response(429, "rate limited"), {"Retry-After": "2"}),
                _make_response(200, _chat_response("recovered")),
            ]
        )
        provider = _make_provider(keys=["sk-key"], transport=transport)
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await provider.call_text(prompt="test", model="m/x")
        mock_sleep.assert_called_once_with(2)
        assert result.content == "recovered"

    async def test_503_with_retry_after_sleeps_and_retries(self):
        """On 503 + Retry-After, provider sleeps and retries same key."""
        transport = _SequenceTransport(
            [
                _make_response(
                    503, _error_response(503, "service unavailable"), {"Retry-After": "5"}
                ),
                _make_response(200, _chat_response("back")),
            ]
        )
        provider = _make_provider(keys=["sk-key"], transport=transport)
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await provider.call_text(prompt="test", model="m/x")
        mock_sleep.assert_called_once_with(5)
        assert result.content == "back"

    async def test_retry_after_capped_at_30_seconds(self):
        """Retry-After values > 30 are capped at 30 seconds."""
        transport = _SequenceTransport(
            [
                _make_response(429, _error_response(429, "rate limited"), {"Retry-After": "120"}),
                _make_response(200, _chat_response("ok")),
            ]
        )
        provider = _make_provider(keys=["sk-key"], transport=transport)
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await provider.call_text(prompt="test", model="m/x")
        mock_sleep.assert_called_once_with(30)

    async def test_429_without_retry_after_no_sleep(self):
        """429 without Retry-After header → no sleep, key rotation only."""
        transport = _SequenceTransport(
            [
                _make_response(429, _error_response(429, "rate limited")),  # no Retry-After
                _make_response(200, _chat_response("next key ok")),
            ]
        )
        provider = _make_provider(keys=["sk-a", "sk-b"], transport=transport)
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await provider.call_text(prompt="test", model="m/x")
        mock_sleep.assert_not_called()
        assert result.content == "next key ok"

    async def test_no_double_retry_on_second_failure(self):
        """If sleep-and-retry also returns 429, key is rotated — not retried again."""
        transport = _SequenceTransport(
            [
                # First key: 429 with Retry-After → sleep → 429 again → rotate
                _make_response(429, _error_response(429, "rate limited"), {"Retry-After": "1"}),
                _make_response(429, _error_response(429, "still limited")),
                # Second key: 200 success
                _make_response(200, _chat_response("second key")),
            ]
        )
        provider = _make_provider(keys=["sk-a", "sk-b"], transport=transport)
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await provider.call_text(prompt="test", model="m/x")
        # Sleep called exactly once (only for the first 429 with Retry-After)
        mock_sleep.assert_called_once_with(1)
        assert result.content == "second key"

    async def test_401_no_retry_after_sleep(self):
        """401 does not trigger Retry-After handling — rotates key directly."""
        transport = _SequenceTransport(
            [
                _make_response(401, _error_response(401, "unauthorized"), {"Retry-After": "10"}),
                _make_response(200, _chat_response("ok")),
            ]
        )
        provider = _make_provider(keys=["sk-dead", "sk-live"], transport=transport)
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await provider.call_text(prompt="test", model="m/x")
        mock_sleep.assert_not_called()
        assert result.content == "ok"

    async def test_400_no_retry_after_sleep(self):
        """400 is non-retriable and does not trigger Retry-After or key rotation."""
        transport = _SequenceTransport(
            [
                _make_response(400, _error_response(400, "bad request"), {"Retry-After": "5"}),
            ]
        )
        provider = _make_provider(keys=["sk-key"], transport=transport)
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(ProviderError):
                await provider.call_text(prompt="test", model="bad/model")
        mock_sleep.assert_not_called()
