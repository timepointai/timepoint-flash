"""Unit tests for Anthropic provider.order rewrite in providers/openrouter.py.

Anthropic prompt caching only activates when OpenRouter routes the request
to Anthropic's official infrastructure.  Third-party hosts that serve the
same model IDs (e.g. AWS Bedrock, Vertex AI) drop ``cache_control`` blocks
silently, so without this rewrite the cache stays cold forever and the
cache_control work in PR #39 is wasted.

Coverage:
    - _provider_order_for_model: pure function behaviour
        - Anthropic model with empty configured order → ["Anthropic"]
        - Anthropic model with configured order → "Anthropic" prepended
        - Anthropic model with "Anthropic" already in order → de-duplicated to front
        - Non-Anthropic model → configured order unchanged
        - Returns a new list (caller cannot mutate provider state)
    - call_text payload integration
        - Anthropic model + empty configured order → provider block with ["Anthropic"]
        - Anthropic model + configured order → "Anthropic" prepended in payload
        - Non-Anthropic model + configured order → unchanged in payload
        - Anthropic model with no _models / no _provider_order still emits provider block
        - require_parameters / allow_fallbacks still set alongside the rewrite

Run with:
    pytest tests/unit/test_openrouter_anthropic_provider_order.py -v
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.core.providers.openrouter import (
    OpenRouterProvider,
    _provider_order_for_model,
)

# ---------------------------------------------------------------------------
# Helpers
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


class _CapturingTransport(httpx.AsyncBaseTransport):
    """Captures every request body and returns a fixed 200 response."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json=_chat_response("captured"))


def _make_provider(
    models: list[str] | None = None,
    provider_order: list[str] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> OpenRouterProvider:
    provider = OpenRouterProvider(
        api_key="sk-or-v1-test",
        models=models,
        provider_order=provider_order,
        base_url="https://openrouter.ai/api/v1",
    )
    provider._client = httpx.AsyncClient(
        base_url="https://openrouter.ai/api/v1",
        transport=transport or _CapturingTransport(),
        headers={
            "HTTP-Referer": "https://timepoint.ai",
            "X-Title": "TIMEPOINT Flash",
            "Content-Type": "application/json",
        },
    )
    return provider


# ---------------------------------------------------------------------------
# _provider_order_for_model — pure function tests
# ---------------------------------------------------------------------------


@pytest.mark.fast
class TestProviderOrderForModel:
    """The helper that decides the effective provider.order list."""

    def test_anthropic_model_empty_order_returns_anthropic(self) -> None:
        """Anthropic model with no configured order → ['Anthropic']."""
        result = _provider_order_for_model("anthropic/claude-3.5-sonnet", [])
        assert result == ["Anthropic"]

    def test_anthropic_model_prepends_to_configured_order(self) -> None:
        """Anthropic model with configured order → 'Anthropic' prepended."""
        result = _provider_order_for_model(
            "anthropic/claude-sonnet-4.5",
            ["Google AI Studio", "Together", "Fireworks"],
        )
        assert result == ["Anthropic", "Google AI Studio", "Together", "Fireworks"]

    def test_anthropic_model_dedupes_existing_anthropic_entry(self) -> None:
        """If 'Anthropic' is already in the order it is moved to the front, not duplicated."""
        result = _provider_order_for_model(
            "anthropic/claude-3-haiku",
            ["Together", "Anthropic", "Fireworks"],
        )
        assert result == ["Anthropic", "Together", "Fireworks"]

    def test_anthropic_model_already_first_unchanged(self) -> None:
        """If 'Anthropic' is already first the order is preserved (still de-duped)."""
        result = _provider_order_for_model(
            "anthropic/claude-3.5-sonnet",
            ["Anthropic", "Google AI Studio"],
        )
        assert result == ["Anthropic", "Google AI Studio"]

    def test_non_anthropic_model_passes_through(self) -> None:
        """Non-Anthropic models receive the configured order unchanged."""
        result = _provider_order_for_model(
            "openai/gpt-4o",
            ["Google AI Studio", "Together"],
        )
        assert result == ["Google AI Studio", "Together"]

    def test_non_anthropic_model_empty_order_stays_empty(self) -> None:
        """Non-Anthropic + empty order → empty (caller decides whether to inject)."""
        assert _provider_order_for_model("openai/gpt-4o", []) == []

    def test_returns_new_list(self) -> None:
        """The returned list must not be the input list (no shared mutable state)."""
        configured = ["Google AI Studio", "Together"]
        result = _provider_order_for_model("openai/gpt-4o", configured)
        assert result == configured
        assert result is not configured

    def test_anthropic_returns_new_list_when_dedupe_noop(self) -> None:
        """Even when no de-dupe happens, the helper must not return the input list."""
        configured = ["Together", "Fireworks"]
        result = _provider_order_for_model("anthropic/claude-3.5-sonnet", configured)
        assert result == ["Anthropic", "Together", "Fireworks"]
        assert result is not configured
        # Original list is unmutated
        assert configured == ["Together", "Fireworks"]

    def test_anthropic_partial_match_does_not_count(self) -> None:
        """A model whose name contains 'anthropic' but no slash prefix is not Anthropic."""
        # Mirrors the existing test_non_anthropic_with_anthropic_in_name_false guarantee
        result = _provider_order_for_model("notanthropica/model", ["Together"])
        assert result == ["Together"]

    def test_empty_model_id_passes_through(self) -> None:
        """An empty model id is not Anthropic — order unchanged."""
        assert _provider_order_for_model("", ["Together"]) == ["Together"]


# ---------------------------------------------------------------------------
# call_text payload — provider.order rewrite integration
# ---------------------------------------------------------------------------


@pytest.mark.fast
@pytest.mark.asyncio
class TestCallTextProviderOrderRewrite:
    """Verify the rewrite is applied in the actual chat/completions request."""

    async def test_anthropic_model_no_configured_order_emits_anthropic(self) -> None:
        """Anthropic model with no configured provider order → ['Anthropic'] in payload."""
        transport = _CapturingTransport()
        provider = _make_provider(models=[], provider_order=[], transport=transport)

        await provider.call_text(
            prompt="What happened in 1776?",
            model="anthropic/claude-3.5-sonnet",
            system="You are a historian.",
        )

        assert len(transport.requests) == 1
        body = json.loads(transport.requests[0].content)
        assert "provider" in body, (
            "Anthropic model must emit a provider block even when no order is configured "
            "— otherwise OpenRouter is free to route to a non-caching host."
        )
        assert body["provider"]["order"] == ["Anthropic"]
        assert body["provider"]["allow_fallbacks"] is True
        assert body["provider"]["require_parameters"] is True

    async def test_anthropic_model_prepends_to_configured_order(self) -> None:
        """Anthropic model with configured order → 'Anthropic' first, others preserved."""
        transport = _CapturingTransport()
        provider = _make_provider(
            models=[],
            provider_order=["Google AI Studio", "Together", "Fireworks"],
            transport=transport,
        )

        await provider.call_text(
            prompt="hello",
            model="anthropic/claude-sonnet-4.5",
        )

        body = json.loads(transport.requests[0].content)
        assert body["provider"]["order"] == [
            "Anthropic",
            "Google AI Studio",
            "Together",
            "Fireworks",
        ]

    async def test_anthropic_model_dedupes_existing_anthropic(self) -> None:
        """Anthropic model with 'Anthropic' already in configured order → moved to front."""
        transport = _CapturingTransport()
        provider = _make_provider(
            models=[],
            provider_order=["Together", "Anthropic", "Fireworks"],
            transport=transport,
        )

        await provider.call_text(prompt="hi", model="anthropic/claude-3.5-sonnet")

        body = json.loads(transport.requests[0].content)
        # No duplicate 'Anthropic' entries — moved to front
        assert body["provider"]["order"] == ["Anthropic", "Together", "Fireworks"]
        assert body["provider"]["order"].count("Anthropic") == 1

    async def test_non_anthropic_model_order_unchanged(self) -> None:
        """Non-Anthropic models keep the configured order unmodified."""
        transport = _CapturingTransport()
        provider = _make_provider(
            models=[],
            provider_order=["Google AI Studio", "Together", "Fireworks"],
            transport=transport,
        )

        await provider.call_text(prompt="hi", model="openai/gpt-4o")

        body = json.loads(transport.requests[0].content)
        assert body["provider"]["order"] == [
            "Google AI Studio",
            "Together",
            "Fireworks",
        ]

    async def test_non_anthropic_model_no_configured_order_no_provider_block(self) -> None:
        """Non-Anthropic + no models[] + empty order → no provider block (existing behaviour)."""
        transport = _CapturingTransport()
        provider = _make_provider(models=[], provider_order=[], transport=transport)

        await provider.call_text(prompt="hi", model="openai/gpt-4o")

        body = json.loads(transport.requests[0].content)
        assert "provider" not in body, (
            "Non-Anthropic with no routing config should keep the request lean — "
            "no provider block to avoid forcing OpenRouter into a single-provider chain."
        )

    async def test_anthropic_model_with_models_list(self) -> None:
        """Anthropic primary + models[] fallback chain still gets Anthropic prepended."""
        transport = _CapturingTransport()
        provider = _make_provider(
            models=["openai/gpt-4o-mini", "google/gemini-2.0-flash-001"],
            provider_order=["Together"],
            transport=transport,
        )

        await provider.call_text(
            prompt="hi",
            model="anthropic/claude-3.5-sonnet",
        )

        body = json.loads(transport.requests[0].content)
        # Anthropic prepended, Together preserved as fallback for the models[] chain
        assert body["provider"]["order"] == ["Anthropic", "Together"]
        # models[] still injected
        assert body["models"] == ["openai/gpt-4o-mini", "google/gemini-2.0-flash-001"]
        # Primary model preserved
        assert body["model"] == "anthropic/claude-3.5-sonnet"

    async def test_provider_state_not_mutated_between_calls(self) -> None:
        """A non-Anthropic call after an Anthropic call must not see a polluted order."""
        transport = _CapturingTransport()
        provider = _make_provider(
            models=[],
            provider_order=["Together", "Fireworks"],
            transport=transport,
        )

        # First call: Anthropic model — should rewrite to ['Anthropic', 'Together', 'Fireworks']
        await provider.call_text(prompt="x", model="anthropic/claude-3.5-sonnet")
        # Second call: non-Anthropic model — should NOT see 'Anthropic' from the previous call
        await provider.call_text(prompt="y", model="openai/gpt-4o")

        first_body = json.loads(transport.requests[0].content)
        second_body = json.loads(transport.requests[1].content)
        assert first_body["provider"]["order"] == ["Anthropic", "Together", "Fireworks"]
        assert second_body["provider"]["order"] == ["Together", "Fireworks"]
        # The provider's own stored order is unchanged
        assert provider._provider_order == ["Together", "Fireworks"]

    async def test_cache_control_and_provider_order_both_applied_for_anthropic(self) -> None:
        """End-to-end: an Anthropic request has BOTH cache_control AND provider.order=['Anthropic'...].

        This is the entire point of the task — the two pieces have to ship together
        for prompt caching to actually fire on Anthropic's side.
        """
        transport = _CapturingTransport()
        provider = _make_provider(
            models=[],
            provider_order=["Google AI Studio"],
            transport=transport,
        )

        await provider.call_text(
            prompt="Tell me about 1776.",
            model="anthropic/claude-3.5-sonnet",
            system="You are a historian with a long, stable system prompt.",
        )

        body = json.loads(transport.requests[0].content)

        # provider.order has Anthropic first
        assert body["provider"]["order"][0] == "Anthropic"

        # system message is wrapped in a list-of-blocks with cache_control
        sys_msg = next(m for m in body["messages"] if m["role"] == "system")
        assert isinstance(sys_msg["content"], list)
        assert sys_msg["content"][0].get("cache_control") == {"type": "ephemeral"}
