"""OpenRouter API provider implementation.

This module provides integration with OpenRouter's multi-model API.
Supports 300+ models including Claude, GPT-4, Llama, and more.

OpenRouter API docs: https://openrouter.ai/docs

Multi-key fallback: When multiple keys are supplied via OPENROUTER_API_KEYS
(comma-separated) the provider iterates through them automatically on
HTTP 401/402/429 or network/timeout errors, logging a WARN with the last-8-char
key fingerprint before advancing. On a non-retriable error (e.g. 400 bad model)
execution stops immediately. If all keys are exhausted an ERROR is logged and
the last error is re-raised.

Native OpenRouter routing (models[] + provider.order): When ``models`` and
``provider_order`` are supplied the provider injects OpenRouter's server-side
failover into every chat/completions request. ``models`` lists fallback model
IDs tried in order when the primary model is unavailable; ``provider_order``
steers OpenRouter to preferred inference providers. ``allow_fallbacks=True``
and ``require_parameters=True`` are always set so the failover chain respects
structured-output and other per-request parameters.

Retry-After handling: On HTTP 429 or 503 the provider checks the ``Retry-After``
response header and, if present, sleeps ``min(Retry-After, 30)`` seconds before
retrying once with the same key. If the retry also fails the key is skipped in
the normal multi-key rotation. HTTP 401/402/400 are never retried via this path.

Prompt caching: For Anthropic models (``anthropic/`` prefix), the provider
injects explicit ``cache_control: {type: ephemeral}`` markers on the system
message so OpenRouter forwards them verbatim to Anthropic's cache layer.
This enables a 5-minute TTL cache that charges 1.25× on the first write and
0.1× on subsequent reads — agents with large, stable system prompts amortise
the write cost after the first scene generation in a session.  For all other
providers (OpenAI, Gemini, DeepSeek, Grok, Groq, Moonshot) OpenRouter caches
automatically when the static prefix is byte-identical across requests; no
markers are needed, so the existing plain-string system message is kept as-is.

Anthropic provider routing: For Anthropic models, the provider also rewrites
``provider.order`` to put ``"Anthropic"`` first so OpenRouter routes the
request to Anthropic's official infrastructure rather than a third-party
host (Together, Fireworks, etc.).  Cache markers only activate when the
underlying inference provider is Anthropic — without this rewrite the
``cache_control`` blocks are dropped at the wire and the cache stays cold
forever.  The configured ``provider_order`` is preserved as a fallback chain
behind ``"Anthropic"`` (de-duplicated if ``"Anthropic"`` was already present),
so non-Anthropic fallback models routed via ``models[]`` still see their
preferred providers.

Cache hit metrics are extracted from ``usage.prompt_tokens_details.cached_tokens``
and ``usage.cache_discount`` in every response and logged at INFO so operators
can confirm savings in production.

Examples:
    >>> from app.core.providers.openrouter import OpenRouterProvider
    >>> provider = OpenRouterProvider(api_key="sk-or-v1-...")
    >>> response = await provider.call_text(
    ...     prompt="Explain quantum computing",
    ...     model="anthropic/claude-3.5-sonnet"
    ... )

Tests:
    - tests/unit/test_providers.py::test_openrouter_provider_init
    - tests/unit/test_providers.py::test_openrouter_provider_call_text
    - tests/unit/test_openrouter_multikey.py  (multi-key fallback matrix)
    - tests/unit/test_openrouter_native_routing.py  (models[], provider.order, Retry-After)
    - tests/unit/test_openrouter_prompt_caching.py  (cache_control injection + metrics)
    - tests/unit/test_openrouter_anthropic_provider_order.py
        (Anthropic provider.order rewrite for prompt caching)
    - tests/integration/test_llm_router.py::test_openrouter_provider_integration
"""

import asyncio
import logging
import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from app.config import ProviderType
from app.core.providers.base import (
    AuthenticationError,
    LLMProvider,
    LLMResponse,
    ProviderError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

# Type variable for structured response models
T = TypeVar("T", bound=BaseModel)

# OpenRouter API configuration
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODELS_URL = f"{OPENROUTER_BASE_URL}/models"
OPENROUTER_CHAT_URL = f"{OPENROUTER_BASE_URL}/chat/completions"

# HTTP status codes that trigger key rotation (try next key)
_RETRIABLE_AUTH_STATUSES: frozenset[int] = frozenset({401, 402, 429, 503})

# HTTP status codes where a Retry-After header is honoured before key rotation
_RETRY_AFTER_STATUSES: frozenset[int] = frozenset({429, 503})

# --- Prompt caching -----------------------------------------------------------
#
# Anthropic models require explicit cache_control markers (max 4 breakpoints per
# request). All other providers listed on OpenRouter (OpenAI, DeepSeek, Gemini,
# Grok / x-ai, Groq, Moonshot) cache automatically when the static prefix is
# byte-identical across requests — no markers needed.
#
# Strategy: place ONE cache breakpoint at the end of the system message.  This
# covers the largest repeated chunk (the full agent system prompt) with a single
# 5-min TTL entry and leaves 3 of the allowed 4 breakpoints free for callers
# that want to add per-conversation caches later.
#
# Minimum cacheable prefix is 1024 tokens for Claude 3.x models.  System
# prompts below that threshold are submitted unchanged — Anthropic silently
# ignores the cache_control, so it is safe to add the marker unconditionally.
#
_EXPLICIT_CACHE_PROVIDER_PREFIXES: tuple[str, ...] = ("anthropic/",)

# OpenRouter provider name (case-sensitive) for Anthropic's official inference
# infrastructure.  Required at the head of ``provider.order`` for any Anthropic
# model so that prompt caching activates — third-party providers serving the
# same model IDs (e.g. AWS Bedrock, Vertex AI) silently strip ``cache_control``.
_ANTHROPIC_PROVIDER_NAME: str = "Anthropic"


def _model_needs_explicit_cache_control(model: str) -> bool:
    """Return True if this model ID requires explicit cache_control markers.

    Anthropic models routed through OpenRouter need an explicit
    ``cache_control: {type: ephemeral}`` block on the system message.
    All other providers (OpenAI, Gemini, DeepSeek, etc.) cache automatically
    when the static prefix is byte-identical — no markers required.
    """
    if not model:
        return False
    return model.startswith(_EXPLICIT_CACHE_PROVIDER_PREFIXES)


def _apply_prompt_cache_control(
    messages: list[dict[str, Any]],
    model: str,
) -> list[dict[str, Any]]:
    """Inject cache_control on the system message for Anthropic models.

    For Anthropic models, transforms the first system message from a plain
    string into a list-of-blocks with a single cache_control marker:

        {"role": "system", "content": "..."}
        ->
        {"role": "system", "content": [{"type": "text", "text": "...",
                                         "cache_control": {"type": "ephemeral"}}]}

    For all other providers the messages list is returned unchanged.

    Args:
        messages: The messages list to (potentially) modify.
        model: The OpenRouter model ID (e.g. "anthropic/claude-3.5-sonnet").

    Returns:
        The messages list, with cache_control applied if appropriate.
    """
    if not _model_needs_explicit_cache_control(model):
        return messages

    result = []
    for msg in messages:
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if isinstance(content, str):
                # Wrap plain string in a list-of-blocks with cache_control
                result.append(
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "text",
                                "text": content,
                                # 5-min TTL @ 1.25x write cost, 0.1x read cost.
                                # One breakpoint per request (out of 4 allowed).
                                "cache_control": {"type": "ephemeral"},
                            }
                        ],
                    }
                )
                continue
        result.append(msg)
    return result


def _provider_order_for_model(model: str, configured_order: list[str]) -> list[str]:
    """Return the effective ``provider.order`` for *model*.

    Anthropic prompt caching only activates when OpenRouter routes the request
    to Anthropic's own infrastructure.  Third-party hosts that serve the same
    model IDs (e.g. AWS Bedrock, Vertex AI) drop the ``cache_control`` blocks
    silently, so the cache never warms up and we keep paying full rate.

    For any ``anthropic/*`` model this helper prepends
    ``"Anthropic"`` to the configured provider order (de-duplicated if it was
    already present).  Configured fallback providers are preserved behind
    Anthropic so the chain still has somewhere to go for non-Anthropic models
    routed via ``models[]``.

    For all other models the configured order is returned unchanged.

    Args:
        model: The OpenRouter model ID (e.g. ``"anthropic/claude-sonnet-4.5"``).
        configured_order: The provider.order list configured on the provider
            instance (typically from ``settings.openrouter_provider_order``).

    Returns:
        A new list — never the input list — to keep callers from mutating
        the provider's stored ``_provider_order``.

    Examples:
        >>> _provider_order_for_model("anthropic/claude-3.5-sonnet", [])
        ['Anthropic']
        >>> _provider_order_for_model(
        ...     "anthropic/claude-3.5-sonnet",
        ...     ["Google AI Studio", "Together"],
        ... )
        ['Anthropic', 'Google AI Studio', 'Together']
        >>> _provider_order_for_model(
        ...     "anthropic/claude-3.5-sonnet",
        ...     ["Together", "Anthropic", "Fireworks"],
        ... )
        ['Anthropic', 'Together', 'Fireworks']
        >>> _provider_order_for_model("openai/gpt-4o", ["Together", "Fireworks"])
        ['Together', 'Fireworks']
    """
    if not _model_needs_explicit_cache_control(model):
        return list(configured_order)

    # De-duplicate: drop any existing Anthropic entry so the prepend leaves a
    # clean single-occurrence ordering.
    rest = [p for p in configured_order if p != _ANTHROPIC_PROVIDER_NAME]
    return [_ANTHROPIC_PROVIDER_NAME, *rest]


def _log_cache_usage(usage: dict[str, Any], model: str, agent: str = "") -> None:
    """Log OpenRouter cache hit / discount metrics.

    Extracts ``usage.prompt_tokens_details.cached_tokens`` and
    ``usage.cache_discount`` from the response body and logs at INFO when
    non-zero so operators can confirm savings in production.  A zero on the
    first call after a cold start is expected and logged at DEBUG to avoid
    spamming the log.

    Args:
        usage: The ``usage`` dict from the OpenRouter response body.
        model: The model ID, included in the log for triage.
        agent: Optional agent name, included in the log when provided.
    """
    details = usage.get("prompt_tokens_details") or {}
    cached_tokens = int(details.get("cached_tokens") or 0)
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    cache_discount = usage.get("cache_discount")
    hit_ratio = (cached_tokens / prompt_tokens) if prompt_tokens else 0.0
    agent_tag = f" agent={agent}" if agent else ""

    if cached_tokens or cache_discount:
        logger.info(
            "prompt_cache%s model=%s cached=%d/%d (%.1f%%) discount=%s",
            agent_tag,
            model,
            cached_tokens,
            prompt_tokens,
            hit_ratio * 100,
            cache_discount if cache_discount is not None else "n/a",
        )
    else:
        logger.debug(
            "prompt_cache%s model=%s cached=0/%d (cold start or non-caching model)",
            agent_tag,
            model,
            prompt_tokens,
        )


class OpenRouterModel(BaseModel):
    """OpenRouter model metadata.

    Attributes:
        id: Model identifier (e.g., "anthropic/claude-3.5-sonnet")
        name: Display name
        context_length: Maximum context window
        pricing: Pricing per token
        architecture: Model architecture info
    """

    id: str
    name: str
    context_length: int
    pricing: dict[str, str]
    architecture: dict[str, Any] | None = None


class OpenRouterProvider(LLMProvider):
    """OpenRouter API provider for multi-model access.

    Provides access to 300+ models via OpenRouter's unified API.
    Supports dynamic model discovery and real-time pricing.

    When initialised with multiple keys (via ``api_keys``) the provider
    iterates through them on auth/rate/network failures so that a single
    exhausted or revoked key does not block generation.

    Attributes:
        provider_type: ProviderType.OPENROUTER
        base_url: API base URL

    Available via OpenRouter:
        - anthropic/claude-3.5-sonnet
        - openai/gpt-4-turbo
        - meta-llama/llama-3.1-405b
        - google/gemini-3-pro-image-preview (Nano Banana Pro)
        - And 300+ more...

    Examples:
        >>> provider = OpenRouterProvider(api_key="sk-or-v1-...")
        >>> models = await provider.list_models()
        >>> response = await provider.call_text(
        ...     prompt="Hello",
        ...     model="anthropic/claude-3.5-sonnet"
        ... )
    """

    provider_type = ProviderType.OPENROUTER

    def __init__(
        self,
        api_key: str = "",
        api_keys: list[str] | None = None,
        base_url: str = OPENROUTER_BASE_URL,
        timeout: float = 60.0,
        models: list[str] | None = None,
        provider_order: list[str] | None = None,
    ) -> None:
        """Initialize OpenRouter provider.

        Args:
            api_key: Single OpenRouter API key (backward-compatible, used when
                     api_keys is not supplied).
            api_keys: Ordered list of OpenRouter API keys for multi-key fallback.
                      When supplied, takes precedence over api_key.
            base_url: API base URL (default: https://openrouter.ai/api/v1).
            timeout: Request timeout in seconds.
            models: Ordered list of fallback model IDs injected as the ``models[]``
                    parameter in chat/completions requests. Tried in order when the
                    primary model is unavailable. Empty list → field omitted.
            provider_order: Ordered list of inference provider names injected as
                            ``provider.order``. Empty list → empty order (OpenRouter
                            chooses). Always sets ``allow_fallbacks=True`` and
                            ``require_parameters=True`` when non-None.
        """
        # Build internal key list (plural wins over singular)
        if api_keys:
            self._keys: list[str] = [k for k in api_keys if k]
        elif api_key:
            self._keys = [api_key]
        else:
            self._keys = []

        # Pass first key (or empty) to base class for backward compat
        super().__init__(self._keys[0] if self._keys else "")
        self.base_url = base_url
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._models: list[str] = models if models is not None else []
        self._provider_order: list[str] = provider_order if provider_order is not None else []

    @property
    def client(self) -> httpx.AsyncClient:
        """Get httpx async client (lazy initialization).

        Note: Authorization is intentionally omitted from client-level headers
        so that per-request keys can be supplied without re-creating the client.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "HTTP-Referer": "https://timepoint.ai",
                    "X-Title": "TIMEPOINT Flash",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _handle_error(self, response: httpx.Response) -> None:
        """Convert HTTP errors to provider errors.

        Args:
            response: The HTTP response.

        Raises:
            AuthenticationError: For 401 errors.
            RateLimitError: For 429 errors.
            ProviderError: For other errors.
        """
        if response.status_code == 401:
            raise AuthenticationError(ProviderType.OPENROUTER)
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                ProviderType.OPENROUTER,
                retry_after=int(retry_after) if retry_after else None,
            )
        else:
            try:
                error_data = response.json()
                message = error_data.get("error", {}).get("message", response.text)
            except Exception:
                message = response.text

            raise ProviderError(
                message=message,
                provider=ProviderType.OPENROUTER,
                status_code=response.status_code,
                retryable=response.status_code >= 500,
            )

    async def _post_with_key_fallback(
        self,
        endpoint: str,
        payload: dict[str, Any],
    ) -> httpx.Response:
        """POST to *endpoint* iterating keys on auth/rate/network failures.

        For each key in ``self._keys``:
        - On HTTP 200: return the response immediately.
        - On HTTP 401/402/429: log WARN (key fingerprint + status), try next.
        - On network/timeout: log WARN (key fingerprint + error), try next.
        - On any other non-200 HTTP status: return the response so the caller
          can invoke ``_handle_error`` (e.g. 400 bad model — non-retriable).

        After all keys are exhausted:
        - Log ERROR with exhausted-key count.
        - Re-raise the last network exception if one occurred, otherwise call
          ``_handle_error`` on the last non-200 response.

        Args:
            endpoint: Relative URL path (e.g. "/chat/completions").
            payload: JSON-serialisable request body.

        Returns:
            httpx.Response with status_code == 200.

        Raises:
            ProviderError: If no keys are configured or all keys are exhausted.
        """
        if not self._keys:
            raise ProviderError(
                message="No OpenRouter API keys configured",
                provider=ProviderType.OPENROUTER,
                retryable=False,
            )

        last_response: httpx.Response | None = None
        last_exc: Exception | None = None

        for key in self._keys:
            fingerprint = f"...{key[-8:]}" if len(key) >= 8 else "???"
            try:
                response = await self.client.post(
                    endpoint,
                    json=payload,
                    headers={"Authorization": f"Bearer {key}"},
                )
                if response.status_code == 200:
                    return response

                # Honour Retry-After on 429 / 503 — sleep once, then retry same key.
                # This handles transient provider-side throttling without burning
                # the next key on what is likely a brief capacity blip.
                # 401 / 402 / 400 are NOT retried via this path.
                if response.status_code in _RETRY_AFTER_STATUSES:
                    retry_after_header = response.headers.get("Retry-After")
                    if retry_after_header:
                        try:
                            sleep_secs = min(int(retry_after_header), 30)
                            logger.info(
                                "OpenRouter key %s: HTTP %d with Retry-After %ds — sleeping",
                                fingerprint,
                                response.status_code,
                                sleep_secs,
                            )
                            await asyncio.sleep(sleep_secs)
                            response = await self.client.post(
                                endpoint,
                                json=payload,
                                headers={"Authorization": f"Bearer {key}"},
                            )
                            if response.status_code == 200:
                                return response
                        except (ValueError, OverflowError):
                            # Malformed Retry-After header — proceed without sleep
                            pass

                if response.status_code in _RETRIABLE_AUTH_STATUSES:
                    logger.warning(
                        "OpenRouter key %s returned HTTP %d, trying next key",
                        fingerprint,
                        response.status_code,
                    )
                    last_response = response
                    continue
                else:
                    # Non-retriable status (e.g. 400 bad model) — return as-is
                    # so the caller can raise the appropriate error.
                    return response
            except httpx.TimeoutException as e:
                logger.warning(
                    "OpenRouter key %s timed out, trying next key",
                    fingerprint,
                )
                last_exc = e
                continue
            except httpx.HTTPError as e:
                logger.warning(
                    "OpenRouter key %s network error: %s, trying next key",
                    fingerprint,
                    e,
                )
                last_exc = e
                continue

        # All keys exhausted
        logger.error(
            "OpenRouter: all %d key(s) exhausted — no successful response",
            len(self._keys),
        )
        if last_exc is not None:
            raise ProviderError(
                message=str(last_exc),
                provider=ProviderType.OPENROUTER,
                retryable=True,
            ) from last_exc
        if last_response is not None:
            self._handle_error(last_response)  # always raises
        raise ProviderError(
            message="All OpenRouter keys exhausted with no response",
            provider=ProviderType.OPENROUTER,
            retryable=False,
        )

    async def list_models(self, capability: str | None = None) -> list[OpenRouterModel]:
        """List available models from OpenRouter.

        Args:
            capability: Filter by capability ("text", "image", "vision").

        Returns:
            List of available models.

        Raises:
            ProviderError: If the API call fails.

        Examples:
            >>> models = await provider.list_models()
            >>> for model in models[:5]:
            ...     print(f"{model.id}: {model.context_length} tokens")
        """
        key = self._keys[0] if self._keys else ""
        response = await self.client.get(
            "/models",
            headers={"Authorization": f"Bearer {key}"} if key else {},
        )

        if response.status_code != 200:
            self._handle_error(response)

        data = response.json()
        models = [OpenRouterModel(**m) for m in data.get("data", [])]

        if capability:
            models = [
                m
                for m in models
                if m.architecture and capability in (m.architecture.get("output_modalities") or [])
            ]

        return models

    async def call_text(
        self,
        prompt: str,
        model: str,
        response_model: type[T] | None = None,
        **kwargs: Any,
    ) -> LLMResponse[T] | LLMResponse[str]:
        """Generate text with optional structured output.

        Uses OpenRouter's chat/completions API. When multiple API keys are
        configured, automatically falls back to the next key on 401/402/429
        or network/timeout errors.

        Args:
            prompt: The input prompt.
            model: Model ID (e.g., "anthropic/claude-3.5-sonnet").
            response_model: Optional Pydantic model for structured output.
            **kwargs: Additional parameters:
                - temperature: Sampling temperature (0.0-2.0)
                - max_tokens: Maximum output tokens
                - system: System message

        Returns:
            LLMResponse containing generated text or structured output.

        Raises:
            ProviderError: If the API call fails.

        Examples:
            >>> response = await provider.call_text(
            ...     prompt="Explain AI",
            ...     model="anthropic/claude-3.5-sonnet",
            ...     temperature=0.7
            ... )
        """
        start_time = time.perf_counter()

        # Build messages.  System message is kept as a plain string here so that
        # string-based operations (e.g. schema hint merging below) can work
        # normally.  Prompt caching transformation happens AFTER all string
        # operations are complete.
        messages: list[dict[str, Any]] = []
        if "system" in kwargs:
            messages.append({"role": "system", "content": kwargs.pop("system")})
        messages.append({"role": "user", "content": prompt})

        # Build request payload
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        # Native OpenRouter server-side routing: model fallbacks + provider preference.
        # models[] lists fallback model IDs tried when the primary model is unavailable.
        # provider.order steers which inference providers handle the request.
        # require_parameters=True ensures fallback providers support all request params
        # (e.g. response_format for structured output).
        #
        # For Anthropic models the order is rewritten to put "Anthropic" first so
        # that the request lands on Anthropic's own infrastructure — third-party
        # hosts strip the cache_control markers and prompt caching never warms.
        # See _provider_order_for_model for full details.
        effective_provider_order = _provider_order_for_model(model, self._provider_order)
        if self._models:
            payload["models"] = self._models
        if self._models or effective_provider_order:
            payload["provider"] = {
                "order": effective_provider_order,
                "allow_fallbacks": True,
                "require_parameters": True,
            }

        # Web search plugins support (e.g. [{"id": "web", "max_results": 5}])
        if "plugins" in kwargs:
            payload["plugins"] = kwargs.pop("plugins")

        # xAI Grok X/Twitter search filter support
        if "x_search_filter" in kwargs:
            payload["x_search_filter"] = kwargs.pop("x_search_filter")

        # Standard OpenRouter parameters
        for param in (
            "temperature",
            "max_tokens",
            "top_p",
            "top_k",
            "frequency_penalty",
            "presence_penalty",
            "repetition_penalty",
            "stop",
        ):
            if param in kwargs:
                payload[param] = kwargs[param]

        # Add response format for structured output
        if response_model is not None:
            payload["response_format"] = {"type": "json_object"}
            # Add explicit schema hint in system message
            # Be very explicit to avoid models returning schema instead of data
            schema = response_model.model_json_schema()
            required_fields = schema.get("required", [])
            properties = schema.get("properties", {})

            # Build example-style prompt with field descriptions
            field_hints = []
            for field_name, field_info in properties.items():
                field_type = field_info.get("type", "any")
                field_desc = field_info.get("description", "")
                if field_desc:
                    field_hints.append(f'  "{field_name}": <{field_type}> - {field_desc}')
                else:
                    field_hints.append(f'  "{field_name}": <{field_type}>')

            fields_str = "\n".join(field_hints)
            schema_message = (
                f"You MUST respond with valid JSON containing actual data values (not a schema definition).\n"
                f"Required fields: {', '.join(required_fields)}\n"
                f"Expected format:\n{{\n{fields_str}\n}}\n"
                f"Fill in actual values based on the request. Do NOT return type definitions."
            )

            if messages and messages[0]["role"] == "system":
                messages[0]["content"] += f"\n\n{schema_message}"
            else:
                messages.insert(0, {"role": "system", "content": schema_message})

        # Apply prompt caching: for Anthropic models, wrap the system message in
        # a list-of-blocks with cache_control so OpenRouter forwards it to
        # Anthropic's cache layer.  This must happen AFTER the schema-hint string
        # concatenation above, but BEFORE the POST.  For all other providers the
        # messages list is returned unchanged (they cache automatically on
        # byte-identical prefix).
        messages = _apply_prompt_cache_control(messages, model)
        payload["messages"] = messages

        try:
            response = await self._post_with_key_fallback("/chat/completions", payload)

            if response.status_code != 200:
                self._handle_error(response)

            data = response.json()
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Extract content and annotations (from web search plugins)
            message_data = data["choices"][0]["message"]
            raw_content = message_data["content"]
            annotations = message_data.get("annotations", [])

            # Parse response
            if response_model is not None and raw_content:
                try:
                    content = response_model.model_validate_json(raw_content)
                except Exception as parse_error:
                    # Try to extract JSON from the response (models sometimes add extra text)
                    import re

                    json_match = re.search(r"\{[\s\S]*\}", raw_content)
                    if json_match:
                        try:
                            content = response_model.model_validate_json(json_match.group())
                        except Exception as e2:
                            logger.warning(f"JSON extraction failed: {e2}")
                            raise ProviderError(
                                message=f"Model returned invalid JSON: {parse_error}. Raw response: {raw_content[:500]}",
                                provider=ProviderType.OPENROUTER,
                                retryable=True,
                            ) from parse_error
                    else:
                        logger.warning(f"No JSON found in response: {raw_content[:200]}")
                        raise ProviderError(
                            message=f"Model did not return JSON: {raw_content[:500]}",
                            provider=ProviderType.OPENROUTER,
                            retryable=True,
                        ) from parse_error
            else:
                content = raw_content or ""

            # Extract usage
            usage_data = data.get("usage", {})
            usage = {
                "input_tokens": usage_data.get("prompt_tokens", 0),
                "output_tokens": usage_data.get("completion_tokens", 0),
            }

            # Log cache hit metrics (cached_tokens / cache_discount).
            # Logged at INFO when non-zero so operators can confirm savings;
            # DEBUG on cold-start / non-caching models to avoid log noise.
            _log_cache_usage(usage_data, model)

            # Build metadata with annotations if present
            response_metadata: dict[str, Any] = {}
            if annotations:
                response_metadata["annotations"] = annotations

            return LLMResponse(
                content=content,
                raw_response=raw_content,
                model=model,
                provider=self.provider_type,
                usage=usage,
                latency_ms=latency_ms,
                metadata=response_metadata,
            )

        except ProviderError:
            raise
        except httpx.HTTPError as e:
            logger.error(f"OpenRouter HTTP error: {e}")
            raise ProviderError(
                message=str(e),
                provider=ProviderType.OPENROUTER,
                retryable=True,
            ) from e

    async def generate_image(
        self,
        prompt: str,
        model: str,
        **kwargs: Any,
    ) -> LLMResponse[str]:
        """Generate an image from a prompt.

        Uses OpenRouter's /chat/completions endpoint with modalities parameter.
        OpenRouter does NOT have a /images/generations endpoint.

        Args:
            prompt: The image generation prompt.
            model: Model ID (e.g., "google/gemini-2.0-flash-exp:free").
            **kwargs: Additional parameters.

        Returns:
            LLMResponse containing base64-encoded image.

        Raises:
            ProviderError: If the API call fails.

        Examples:
            >>> response = await provider.generate_image(
            ...     prompt="A sunset over mountains",
            ...     model="google/gemini-2.0-flash-exp:free"
            ... )
        """
        import re

        start_time = time.perf_counter()

        # OpenRouter uses /chat/completions with modalities for image generation
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": f"Generate an image: {prompt}",
                }
            ],
            # Image-only models (FLUX) need ["image"]; multimodal models need both
            "modalities": ["image"] if "flux" in model.lower() else ["image", "text"],
        }

        try:
            response = await self._post_with_key_fallback("/chat/completions", payload)

            if response.status_code != 200:
                self._handle_error(response)

            data = response.json()
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Extract image from response - OpenRouter returns images in content
            message = data.get("choices", [{}])[0].get("message", {})
            content_parts = message.get("content", [])

            # Content can be a string or list of parts
            image_b64 = None

            if isinstance(content_parts, str):
                # Check if it's a data URL
                match = re.match(r"data:image/[^;]+;base64,(.+)", content_parts)
                if match:
                    image_b64 = match.group(1)
                else:
                    # Might be raw base64
                    image_b64 = content_parts
            elif isinstance(content_parts, list):
                # Look for image part in multimodal response
                for part in content_parts:
                    if isinstance(part, dict):
                        # Check for inline_data format (Gemini style)
                        if "inline_data" in part:
                            image_b64 = part["inline_data"].get("data")
                            break
                        # Check for image_url format
                        if part.get("type") == "image_url":
                            url = part.get("image_url", {}).get("url", "")
                            match = re.match(r"data:image/[^;]+;base64,(.+)", url)
                            if match:
                                image_b64 = match.group(1)
                                break
                        # Check for image type directly
                        if part.get("type") == "image":
                            image_b64 = part.get("data") or part.get("image")
                            break

            if not image_b64:
                # Log what we got for debugging
                logger.error(f"OpenRouter image response format unexpected: {data}")
                raise ProviderError(
                    message=f"No image found in OpenRouter response. Got: {str(data)[:500]}",
                    provider=ProviderType.OPENROUTER,
                    retryable=False,
                )

            return LLMResponse(
                content=image_b64,
                model=model,
                provider=self.provider_type,
                latency_ms=latency_ms,
            )

        except ProviderError:
            raise
        except httpx.HTTPError as e:
            logger.error(f"OpenRouter image generation error: {e}")
            raise ProviderError(
                message=str(e),
                provider=ProviderType.OPENROUTER,
                retryable=True,
            ) from e

    async def analyze_image(
        self,
        image: str,
        prompt: str,
        model: str,
        **kwargs: Any,
    ) -> LLMResponse[dict[str, Any]]:
        """Analyze an image with a prompt.

        Uses vision-capable models via OpenRouter.

        Args:
            image: Base64-encoded image or URL.
            prompt: The analysis prompt.
            model: Model ID with vision capability.
            **kwargs: Additional parameters.

        Returns:
            LLMResponse containing analysis results.

        Raises:
            ProviderError: If the API call fails.

        Examples:
            >>> response = await provider.analyze_image(
            ...     image="https://example.com/image.jpg",
            ...     prompt="Describe this image",
            ...     model="anthropic/claude-3.5-sonnet"
            ... )
        """
        start_time = time.perf_counter()

        # Build content with image
        if image.startswith(("http://", "https://")):
            image_content = {
                "type": "image_url",
                "image_url": {"url": image},
            }
        else:
            # Base64 encoded
            image_content = {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image}"},
            }

        messages = [
            {
                "role": "user",
                "content": [
                    image_content,
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        try:
            response = await self._post_with_key_fallback("/chat/completions", payload)

            if response.status_code != 200:
                self._handle_error(response)

            data = response.json()
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            raw_content = data["choices"][0]["message"]["content"]

            # Try to parse as JSON, otherwise wrap in dict
            import json

            try:
                content = json.loads(raw_content)
            except json.JSONDecodeError:
                content = {"analysis": raw_content}

            # Extract usage
            usage_data = data.get("usage", {})
            usage = {
                "input_tokens": usage_data.get("prompt_tokens", 0),
                "output_tokens": usage_data.get("completion_tokens", 0),
            }

            return LLMResponse(
                content=content,
                raw_response=raw_content,
                model=model,
                provider=self.provider_type,
                usage=usage,
                latency_ms=latency_ms,
            )

        except ProviderError:
            raise
        except httpx.HTTPError as e:
            logger.error(f"OpenRouter vision error: {e}")
            raise ProviderError(
                message=str(e),
                provider=ProviderType.OPENROUTER,
                retryable=True,
            ) from e

    async def health_check(self) -> bool:
        """Check if OpenRouter provider is accessible.

        Makes a minimal API call to verify connectivity.

        Returns:
            bool: True if provider is healthy.
        """
        try:
            key = self._keys[0] if self._keys else ""
            # Just check models endpoint - doesn't require completion tokens
            response = await self.client.get(
                "/models",
                headers={"Authorization": f"Bearer {key}"} if key else {},
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"OpenRouter health check failed: {e}")
            return False
