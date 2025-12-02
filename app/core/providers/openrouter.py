"""OpenRouter API provider implementation.

This module provides integration with OpenRouter's multi-model API.
Supports 300+ models including Claude, GPT-4, Llama, and more.

OpenRouter API docs: https://openrouter.ai/docs

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
    - tests/integration/test_llm_router.py::test_openrouter_provider_integration
"""

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

    Attributes:
        provider_type: ProviderType.OPENROUTER
        api_key: OpenRouter API key
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
        api_key: str,
        base_url: str = OPENROUTER_BASE_URL,
        timeout: float = 60.0,
    ) -> None:
        """Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key.
            base_url: API base URL (default: https://openrouter.ai/api/v1).
            timeout: Request timeout in seconds.
        """
        super().__init__(api_key)
        self.base_url = base_url
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get httpx async client (lazy initialization)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
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
        response = await self.client.get("/models")

        if response.status_code != 200:
            self._handle_error(response)

        data = response.json()
        models = [OpenRouterModel(**m) for m in data.get("data", [])]

        if capability:
            models = [
                m
                for m in models
                if m.architecture
                and capability in m.architecture.get("modality", "")
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

        Uses OpenRouter's chat/completions API.

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

        # Build messages
        messages: list[dict[str, str]] = []
        if "system" in kwargs:
            messages.append({"role": "system", "content": kwargs.pop("system")})
        messages.append({"role": "user", "content": prompt})

        # Build request payload
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]

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

        try:
            response = await self.client.post("/chat/completions", json=payload)

            if response.status_code != 200:
                self._handle_error(response)

            data = response.json()
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Extract content
            raw_content = data["choices"][0]["message"]["content"]

            # Parse response
            if response_model is not None and raw_content:
                try:
                    content = response_model.model_validate_json(raw_content)
                except Exception as parse_error:
                    # Try to extract JSON from the response (models sometimes add extra text)
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', raw_content)
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

            return LLMResponse(
                content=content,
                raw_response=raw_content,
                model=model,
                provider=self.provider_type,
                usage=usage,
                latency_ms=latency_ms,
            )

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

        Uses OpenRouter's image generation models (e.g., Nano Banana Pro).

        Args:
            prompt: The image generation prompt.
            model: Model ID (e.g., "google/gemini-3-pro-image-preview").
            **kwargs: Additional parameters.

        Returns:
            LLMResponse containing base64-encoded image or URL.

        Raises:
            ProviderError: If the API call fails.

        Examples:
            >>> response = await provider.generate_image(
            ...     prompt="A sunset over mountains",
            ...     model="google/gemini-3-pro-image-preview"
            ... )
        """
        start_time = time.perf_counter()

        # OpenRouter uses chat completions for image models too
        # The response includes an image URL or base64
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            response = await self.client.post("/chat/completions", json=payload)

            if response.status_code != 200:
                self._handle_error(response)

            data = response.json()
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Extract image from response
            # Note: Different models return images differently
            content = data["choices"][0]["message"]["content"]

            # If content is a URL, return it; otherwise assume base64
            # This may need adjustment based on specific model responses

            return LLMResponse(
                content=content,
                model=model,
                provider=self.provider_type,
                latency_ms=latency_ms,
            )

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
            response = await self.client.post("/chat/completions", json=payload)

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
            # Just check models endpoint - doesn't require completion tokens
            response = await self.client.get("/models")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"OpenRouter health check failed: {e}")
            return False
