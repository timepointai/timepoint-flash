"""Unit tests for OpenRouter prompt caching in providers/openrouter.py.

Tests the cache_control injection (_apply_prompt_cache_control) and cache
usage logging (_log_cache_usage) helpers, plus the full call_text path.

Coverage:
    - _model_needs_explicit_cache_control: Anthropic prefix detection
    - _apply_prompt_cache_control: system message restructuring for Anthropic
    - _apply_prompt_cache_control: pass-through for non-Anthropic models
    - _log_cache_usage: INFO when cached_tokens > 0
    - _log_cache_usage: DEBUG on cold start (zero cached tokens)
    - call_text: cache_control present in payload for Anthropic model
    - call_text: no cache_control in payload for non-Anthropic model
    - call_text: schema hint included inside cached system block

Run with:
    pytest tests/unit/test_openrouter_prompt_caching.py -v
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
import pytest

from app.core.providers.openrouter import (
    OpenRouterProvider,
    _apply_prompt_cache_control,
    _log_cache_usage,
    _model_needs_explicit_cache_control,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chat_response(
    content: str = "hello",
    cached_tokens: int = 0,
    cache_discount: float | None = None,
) -> dict[str, Any]:
    """Minimal OpenRouter /chat/completions success payload."""
    usage: dict[str, Any] = {
        "prompt_tokens": 500,
        "completion_tokens": 50,
        "prompt_tokens_details": {"cached_tokens": cached_tokens},
    }
    if cache_discount is not None:
        usage["cache_discount"] = cache_discount
    return {
        "choices": [
            {
                "message": {"content": content, "role": "assistant"},
                "finish_reason": "stop",
            }
        ],
        "usage": usage,
    }


class _SingleResponse(httpx.AsyncBaseTransport):
    """Return a single 200 response for any POST."""

    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=self._body)


def _make_provider(body: dict[str, Any]) -> OpenRouterProvider:
    provider = OpenRouterProvider(api_key="sk-or-v1-testkey")
    provider._client = httpx.AsyncClient(
        transport=_SingleResponse(body),
        base_url="https://openrouter.ai/api/v1",
    )
    return provider


# ---------------------------------------------------------------------------
# _model_needs_explicit_cache_control
# ---------------------------------------------------------------------------


class TestModelNeedsExplicitCacheControl:
    def test_anthropic_prefix_true(self) -> None:
        assert _model_needs_explicit_cache_control("anthropic/claude-3.5-sonnet") is True

    def test_anthropic_haiku_true(self) -> None:
        assert _model_needs_explicit_cache_control("anthropic/claude-3-haiku") is True

    def test_openai_false(self) -> None:
        assert _model_needs_explicit_cache_control("openai/gpt-4o") is False

    def test_google_false(self) -> None:
        assert _model_needs_explicit_cache_control("google/gemini-2.0-flash-001") is False

    def test_empty_false(self) -> None:
        assert _model_needs_explicit_cache_control("") is False

    def test_non_anthropic_with_anthropic_in_name_false(self) -> None:
        # "notanthropica/model" should NOT match
        assert _model_needs_explicit_cache_control("notanthropica/model") is False


# ---------------------------------------------------------------------------
# _apply_prompt_cache_control
# ---------------------------------------------------------------------------


class TestApplyPromptCacheControl:
    def test_anthropic_wraps_system_content(self) -> None:
        messages = [
            {"role": "system", "content": "You are a historian."},
            {"role": "user", "content": "Tell me about Rome."},
        ]
        result = _apply_prompt_cache_control(messages, "anthropic/claude-3.5-sonnet")

        sys_msg = result[0]
        assert sys_msg["role"] == "system"
        assert isinstance(sys_msg["content"], list)
        assert len(sys_msg["content"]) == 1
        block = sys_msg["content"][0]
        assert block["type"] == "text"
        assert block["text"] == "You are a historian."
        assert block["cache_control"] == {"type": "ephemeral"}

    def test_anthropic_user_message_unchanged(self) -> None:
        messages = [
            {"role": "system", "content": "System prompt."},
            {"role": "user", "content": "User question."},
        ]
        result = _apply_prompt_cache_control(messages, "anthropic/claude-3.5-sonnet")
        user_msg = result[1]
        assert user_msg["role"] == "user"
        assert user_msg["content"] == "User question."

    def test_non_anthropic_passes_through_unchanged(self) -> None:
        messages = [
            {"role": "system", "content": "System prompt."},
            {"role": "user", "content": "User question."},
        ]
        result = _apply_prompt_cache_control(messages, "openai/gpt-4o")
        # Content stays as plain string
        assert isinstance(result[0]["content"], str)
        assert result[0]["content"] == "System prompt."

    def test_no_system_message_unchanged(self) -> None:
        messages = [{"role": "user", "content": "Hello."}]
        result = _apply_prompt_cache_control(messages, "anthropic/claude-3.5-sonnet")
        assert result == messages

    def test_already_list_content_untouched(self) -> None:
        """If system content is already a list, don't double-wrap."""
        existing_block = [{"type": "text", "text": "Already a block."}]
        messages = [
            {"role": "system", "content": existing_block},
            {"role": "user", "content": "Hi."},
        ]
        result = _apply_prompt_cache_control(messages, "anthropic/claude-3.5-sonnet")
        # Non-string content is not modified
        assert result[0]["content"] is existing_block

    def test_preserves_message_order(self) -> None:
        messages = [
            {"role": "system", "content": "Sys."},
            {"role": "user", "content": "Q1."},
        ]
        result = _apply_prompt_cache_control(messages, "anthropic/claude-3.5-sonnet")
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"


# ---------------------------------------------------------------------------
# _log_cache_usage
# ---------------------------------------------------------------------------


class TestLogCacheUsage:
    def test_logs_info_on_cache_hit(self, caplog: pytest.LogCaptureFixture) -> None:
        usage = {
            "prompt_tokens": 1000,
            "prompt_tokens_details": {"cached_tokens": 800},
            "cache_discount": 0.1,
        }
        with caplog.at_level(logging.INFO, logger="app.core.providers.openrouter"):
            _log_cache_usage(usage, "anthropic/claude-3.5-sonnet")

        assert any("prompt_cache" in r.message for r in caplog.records)
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert info_records, "Expected at least one INFO log"
        assert "800" in info_records[0].message  # cached token count
        assert "80.0" in info_records[0].message  # hit ratio

    def test_logs_debug_on_cold_start(self, caplog: pytest.LogCaptureFixture) -> None:
        usage = {
            "prompt_tokens": 500,
            "prompt_tokens_details": {"cached_tokens": 0},
        }
        with caplog.at_level(logging.DEBUG, logger="app.core.providers.openrouter"):
            _log_cache_usage(usage, "anthropic/claude-3.5-sonnet")

        debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
        assert debug_records, "Expected at least one DEBUG log"
        assert "cold start" in debug_records[0].message

    def test_no_info_logged_on_zero_tokens(self, caplog: pytest.LogCaptureFixture) -> None:
        usage: dict[str, Any] = {
            "prompt_tokens": 500,
            "prompt_tokens_details": {"cached_tokens": 0},
        }
        with caplog.at_level(logging.INFO, logger="app.core.providers.openrouter"):
            _log_cache_usage(usage, "openai/gpt-4o")
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert not info_records, "Should not log INFO when no tokens cached"

    def test_agent_tag_included(self, caplog: pytest.LogCaptureFixture) -> None:
        usage = {
            "prompt_tokens": 800,
            "prompt_tokens_details": {"cached_tokens": 600},
        }
        with caplog.at_level(logging.INFO, logger="app.core.providers.openrouter"):
            _log_cache_usage(usage, "anthropic/claude-3.5-sonnet", agent="JudgeAgent")
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert any("JudgeAgent" in r.message for r in info_records)


# ---------------------------------------------------------------------------
# call_text integration: cache_control in payload
# ---------------------------------------------------------------------------


class TestCallTextCacheControl:
    @pytest.mark.asyncio
    async def test_anthropic_model_injects_cache_control(self) -> None:
        """Payload sent to OpenRouter has cache_control on the system block."""
        captured: list[dict[str, Any]] = []

        class _CapturingTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                body = json.loads(request.content)
                captured.append(body)
                return httpx.Response(200, json=_chat_response("result"))

        provider = OpenRouterProvider(api_key="sk-or-v1-testkey")
        provider._client = httpx.AsyncClient(
            transport=_CapturingTransport(),
            base_url="https://openrouter.ai/api/v1",
        )

        await provider.call_text(
            prompt="What happened in 1776?",
            model="anthropic/claude-3.5-sonnet",
            system="You are a historian.",
        )

        assert captured, "No request captured"
        payload = captured[0]
        sys_msg = next(m for m in payload["messages"] if m["role"] == "system")
        assert isinstance(sys_msg["content"], list), "System content should be a list for Anthropic"
        block = sys_msg["content"][0]
        assert block.get("cache_control") == {"type": "ephemeral"}
        assert block.get("text") == "You are a historian."

    @pytest.mark.asyncio
    async def test_non_anthropic_model_no_cache_control(self) -> None:
        """For non-Anthropic models, system content stays as a plain string."""
        captured: list[dict[str, Any]] = []

        class _CapturingTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                body = json.loads(request.content)
                captured.append(body)
                return httpx.Response(200, json=_chat_response("result"))

        provider = OpenRouterProvider(api_key="sk-or-v1-testkey")
        provider._client = httpx.AsyncClient(
            transport=_CapturingTransport(),
            base_url="https://openrouter.ai/api/v1",
        )

        await provider.call_text(
            prompt="What happened in 1776?",
            model="google/gemini-2.0-flash-001",
            system="You are a historian.",
        )

        assert captured
        payload = captured[0]
        sys_msg = next(m for m in payload["messages"] if m["role"] == "system")
        assert isinstance(sys_msg["content"], str), "System content should stay as string for non-Anthropic"

    @pytest.mark.asyncio
    async def test_schema_hint_included_in_cached_block(self) -> None:
        """When response_model is used, schema hint is inside the cached system block."""
        from pydantic import BaseModel as PM

        class _Out(PM):
            answer: str

        captured: list[dict[str, Any]] = []

        class _CapturingTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                body = json.loads(request.content)
                captured.append(body)
                return httpx.Response(
                    200, json=_chat_response('{"answer": "test answer"}')
                )

        provider = OpenRouterProvider(api_key="sk-or-v1-testkey")
        provider._client = httpx.AsyncClient(
            transport=_CapturingTransport(),
            base_url="https://openrouter.ai/api/v1",
        )

        await provider.call_text(
            prompt="Summarise this.",
            model="anthropic/claude-3.5-sonnet",
            response_model=_Out,
            system="You are a summariser.",
        )

        assert captured
        payload = captured[0]
        sys_msg = next(m for m in payload["messages"] if m["role"] == "system")
        # Should be a list-of-blocks (Anthropic cache form)
        assert isinstance(sys_msg["content"], list)
        block_text = sys_msg["content"][0]["text"]
        # Schema hint should be inside the cached block
        assert "answer" in block_text
        assert "cache_control" in sys_msg["content"][0]

    @pytest.mark.asyncio
    async def test_cache_metrics_logged_on_hit(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """INFO log emitted when response contains cached_tokens > 0."""
        provider = _make_provider(_chat_response("ok", cached_tokens=450, cache_discount=0.08))

        with caplog.at_level(logging.INFO, logger="app.core.providers.openrouter"):
            await provider.call_text(
                prompt="Hello",
                model="anthropic/claude-3.5-sonnet",
            )

        info_msgs = [r.message for r in caplog.records if r.levelno == logging.INFO]
        assert any("prompt_cache" in m for m in info_msgs)
        assert any("450" in m for m in info_msgs)

    @pytest.mark.asyncio
    async def test_no_system_message_still_works(self) -> None:
        """call_text without a system kwarg completes without error."""
        provider = _make_provider(_chat_response("answer"))
        response = await provider.call_text(
            prompt="What is 2+2?",
            model="anthropic/claude-3.5-sonnet",
        )
        assert response.content == "answer"
