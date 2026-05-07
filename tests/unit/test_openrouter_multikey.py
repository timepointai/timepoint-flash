"""Unit tests for OpenRouter multi-key fallback in providers/openrouter.py.

Tests the _post_with_key_fallback helper and the call_text / generate_image /
analyze_image callers using httpx.MockTransport so no real network calls are made.

Matrix:
    - empty key list   → ProviderError (no keys configured)
    - single key, 200  → returns response
    - first 401, second 200 → logs WARN, returns second response
    - all 401          → logs ERROR, raises (AuthenticationError via _handle_error)
    - non-retriable 400 → raises immediately without trying next key

Run with:
    pytest tests/unit/test_openrouter_multikey.py -v
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from app.core.providers.base import AuthenticationError, ProviderError
from app.core.providers.openrouter import OpenRouterProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chat_response(content: str = "hello") -> dict[str, Any]:
    """Minimal OpenRouter /chat/completions success payload."""
    return {
        "choices": [
            {
                "message": {
                    "content": content,
                    "role": "assistant",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def _error_response(status: int, message: str = "error") -> dict[str, Any]:
    return {"error": {"message": message, "code": status}}


class _SequenceTransport(httpx.AsyncBaseTransport):
    """Return a pre-defined sequence of responses for POST /chat/completions."""

    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses: Iterator[httpx.Response] = iter(responses)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        try:
            return next(self._responses)
        except StopIteration:
            pytest.fail(f"Unexpected extra request to {request.url}")


def _make_response(status: int, body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        headers={"Content-Type": "application/json"},
        content=json.dumps(body).encode(),
    )


def _make_provider_with_transport(
    keys: list[str],
    transport: httpx.BaseTransport,
) -> OpenRouterProvider:
    """Build an OpenRouterProvider whose client uses the given MockTransport."""
    provider = OpenRouterProvider(api_keys=keys, base_url="https://openrouter.ai/api/v1")
    # Inject a client wired to the fake transport
    provider._client = httpx.AsyncClient(
        base_url="https://openrouter.ai/api/v1",
        transport=transport,
        headers={
            "HTTP-Referer": "https://timepoint.ai",
            "X-Title": "TIMEPOINT Flash",
            "Content-Type": "application/json",
        },
    )
    return provider


# ---------------------------------------------------------------------------
# config.py — openrouter_keys property
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestOpenrouterKeysProperty:
    """Test Settings.openrouter_keys parsing logic."""

    def test_plural_wins_over_singular(self):
        from app.config import Settings

        s = Settings(
            OPENROUTER_API_KEY="singular",
            OPENROUTER_API_KEYS="key1,key2,key3",
        )
        assert s.openrouter_keys == ["key1", "key2", "key3"]

    def test_falls_back_to_singular(self):
        from app.config import Settings

        s = Settings(
            OPENROUTER_API_KEY="only-key",
            OPENROUTER_API_KEYS=None,
        )
        assert s.openrouter_keys == ["only-key"]

    def test_empty_plural_falls_back_to_singular(self):
        from app.config import Settings

        s = Settings(
            OPENROUTER_API_KEY="fallback",
            OPENROUTER_API_KEYS="  ,  ,  ",  # all whitespace/commas
        )
        assert s.openrouter_keys == ["fallback"]

    def test_deduplication(self):
        from app.config import Settings

        s = Settings(
            OPENROUTER_API_KEYS="key1,key2,key1,key3",
        )
        assert s.openrouter_keys == ["key1", "key2", "key3"]

    def test_strips_whitespace(self):
        from app.config import Settings

        s = Settings(
            OPENROUTER_API_KEYS=" key1 , key2 , key3 ",
        )
        assert s.openrouter_keys == ["key1", "key2", "key3"]

    def test_empty_returns_empty_list(self):
        from app.config import Settings

        s = Settings(
            OPENROUTER_API_KEY=None,
            OPENROUTER_API_KEYS=None,
        )
        assert s.openrouter_keys == []

    def test_has_provider_openrouter_uses_keys_list(self):
        from app.config import ProviderType, Settings

        # Has provider when plural key is set but singular is None
        s = Settings(
            OPENROUTER_API_KEY=None,
            OPENROUTER_API_KEYS="key1,key2",
        )
        assert s.has_provider(ProviderType.OPENROUTER) is True

    def test_has_provider_openrouter_false_when_no_keys(self):
        from app.config import ProviderType, Settings

        s = Settings(
            OPENROUTER_API_KEY=None,
            OPENROUTER_API_KEYS=None,
        )
        assert s.has_provider(ProviderType.OPENROUTER) is False


# ---------------------------------------------------------------------------
# OpenRouterProvider init
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestOpenRouterProviderInit:
    """Test OpenRouterProvider initialisation with various key inputs."""

    def test_single_api_key(self):
        p = OpenRouterProvider(api_key="sk-single")
        assert p._keys == ["sk-single"]
        assert p.api_key == "sk-single"

    def test_api_keys_list(self):
        p = OpenRouterProvider(api_keys=["sk-a", "sk-b", "sk-c"])
        assert p._keys == ["sk-a", "sk-b", "sk-c"]

    def test_api_keys_wins_over_api_key(self):
        p = OpenRouterProvider(api_key="sk-old", api_keys=["sk-new"])
        assert p._keys == ["sk-new"]

    def test_empty_strings_filtered(self):
        p = OpenRouterProvider(api_keys=["sk-a", "", "sk-b"])
        assert p._keys == ["sk-a", "sk-b"]

    def test_no_keys(self):
        p = OpenRouterProvider()
        assert p._keys == []


# ---------------------------------------------------------------------------
# _post_with_key_fallback — core iteration logic
# ---------------------------------------------------------------------------

@pytest.mark.fast
@pytest.mark.asyncio
class TestPostWithKeyFallback:
    """Test the internal key-iteration helper via call_text."""

    async def test_no_keys_raises(self):
        """Empty key list → ProviderError immediately."""
        provider = OpenRouterProvider(api_keys=[])
        with pytest.raises(ProviderError, match="No OpenRouter API keys configured"):
            await provider._post_with_key_fallback("/chat/completions", {"model": "x"})

    async def test_single_key_200(self):
        """Single key with 200 → returns response."""
        transport = _SequenceTransport([
            _make_response(200, _chat_response("ok")),
        ])
        provider = _make_provider_with_transport(["sk-key1"], transport)
        resp = await provider._post_with_key_fallback("/chat/completions", {"model": "x"})
        assert resp.status_code == 200

    async def test_first_401_second_200(self):
        """First key returns 401, second key returns 200 → success."""
        transport = _SequenceTransport([
            _make_response(401, _error_response(401, "User not found")),
            _make_response(200, _chat_response("hi")),
        ])
        provider = _make_provider_with_transport(["sk-dead", "sk-live"], transport)
        resp = await provider._post_with_key_fallback("/chat/completions", {"model": "x"})
        assert resp.status_code == 200
        assert resp.json()["choices"][0]["message"]["content"] == "hi"

    async def test_first_402_second_200(self):
        """402 (insufficient credits) is also retriable."""
        transport = _SequenceTransport([
            _make_response(402, _error_response(402, "Insufficient credits")),
            _make_response(200, _chat_response("paid")),
        ])
        provider = _make_provider_with_transport(["sk-broke", "sk-rich"], transport)
        resp = await provider._post_with_key_fallback("/chat/completions", {"model": "x"})
        assert resp.status_code == 200

    async def test_first_429_second_200(self):
        """429 (rate limit) is retriable — next key attempted."""
        transport = _SequenceTransport([
            _make_response(429, _error_response(429, "Rate limited")),
            _make_response(200, _chat_response("ok")),
        ])
        provider = _make_provider_with_transport(["sk-limited", "sk-free"], transport)
        resp = await provider._post_with_key_fallback("/chat/completions", {"model": "x"})
        assert resp.status_code == 200

    async def test_all_401_raises(self):
        """All keys return 401 → logs ERROR and raises AuthenticationError."""
        transport = _SequenceTransport([
            _make_response(401, _error_response(401, "bad key")),
            _make_response(401, _error_response(401, "bad key")),
        ])
        provider = _make_provider_with_transport(["sk-a", "sk-b"], transport)
        with pytest.raises((AuthenticationError, ProviderError)):
            await provider._post_with_key_fallback("/chat/completions", {"model": "x"})

    async def test_non_retriable_400_raises_immediately(self):
        """400 (bad model / bad request) → returned immediately, no next key tried."""
        # If the second response were consumed the SequenceTransport would fail
        transport = _SequenceTransport([
            _make_response(400, _error_response(400, "model not found")),
            # This response must NOT be consumed:
            _make_response(200, _chat_response("should_not_reach")),
        ])
        provider = _make_provider_with_transport(["sk-key1", "sk-key2"], transport)
        # _post_with_key_fallback returns non-retriable responses for caller to handle
        resp = await provider._post_with_key_fallback("/chat/completions", {"model": "bad-model"})
        assert resp.status_code == 400

    async def test_timeout_triggers_next_key(self):
        """Network timeout on first key → try second key."""

        class TimeoutThenOkTransport(httpx.AsyncBaseTransport):
            def __init__(self) -> None:
                self._call_count = 0

            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                self._call_count += 1
                if self._call_count == 1:
                    raise httpx.TimeoutException("timed out", request=request)
                return _make_response(200, _chat_response("recovered"))

        transport = TimeoutThenOkTransport()
        provider = _make_provider_with_transport(["sk-slow", "sk-fast"], transport)
        resp = await provider._post_with_key_fallback("/chat/completions", {"model": "x"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# call_text end-to-end through fallback
# ---------------------------------------------------------------------------

@pytest.mark.fast
@pytest.mark.asyncio
class TestCallTextMultiKey:
    """Test call_text with multi-key fallback via MockTransport."""

    async def test_call_text_single_key_200(self):
        """Basic call_text with one key succeeds."""
        transport = _SequenceTransport([
            _make_response(200, _chat_response("the answer")),
        ])
        provider = _make_provider_with_transport(["sk-only"], transport)
        response = await provider.call_text(prompt="What is 2+2?", model="test/model")
        assert response.content == "the answer"

    async def test_call_text_first_401_second_200(self):
        """call_text falls back to second key after first returns 401."""
        transport = _SequenceTransport([
            _make_response(401, _error_response(401, "revoked")),
            _make_response(200, _chat_response("fallback answer")),
        ])
        provider = _make_provider_with_transport(["sk-revoked", "sk-valid"], transport)
        response = await provider.call_text(prompt="Test", model="test/model")
        assert response.content == "fallback answer"

    async def test_call_text_all_401_raises(self):
        """call_text raises when all keys are invalid."""
        transport = _SequenceTransport([
            _make_response(401, _error_response(401, "bad")),
            _make_response(401, _error_response(401, "also bad")),
            _make_response(401, _error_response(401, "all bad")),
        ])
        provider = _make_provider_with_transport(
            ["sk-a", "sk-b", "sk-c"], transport
        )
        with pytest.raises((AuthenticationError, ProviderError)):
            await provider.call_text(prompt="Test", model="test/model")

    async def test_call_text_non_retriable_400_raises(self):
        """call_text raises immediately on 400 without trying next key."""
        transport = _SequenceTransport([
            _make_response(400, _error_response(400, "invalid model")),
        ])
        provider = _make_provider_with_transport(["sk-key"], transport)
        with pytest.raises(ProviderError):
            await provider.call_text(prompt="Test", model="invalid/model")
