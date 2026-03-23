"""Stability AI REST API provider implementation.

This module provides integration with Stability AI's image generation models
via the REST API. Supports SD3.5 Large for permissive/distillable image generation.

Stability AI API docs: https://platform.stability.ai/docs/api-reference

Examples:
    >>> from app.core.providers.stability import StabilityProvider
    >>> provider = StabilityProvider(api_key="sk-...")
    >>> response = await provider.generate_image(
    ...     prompt="A sunset over mountains",
    ...     model="stability-ai/sd3.5-large"
    ... )

Tests:
    - tests/unit/test_providers.py::test_stability_provider_init
    - tests/unit/test_providers.py::test_stability_provider_generate_image
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

T = TypeVar("T", bound=BaseModel)

# Stability AI API configuration
STABILITY_API_BASE = "https://api.stability.ai"
STABILITY_SD3_ENDPOINT = f"{STABILITY_API_BASE}/v2beta/stable-image/generate/sd3"

# Model ID to Stability API model parameter mapping
STABILITY_MODEL_MAP = {
    "stability-ai/sd3.5-large": "sd3.5-large",
}

# Default generation parameters
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_OUTPUT_FORMAT = "png"


class StabilityProvider(LLMProvider):
    """Stability AI REST API provider for image generation.

    Uses the Stability AI REST API for SD3.5 image generation.
    SD3.5 Large allows downstream distillation, making it suitable
    for the permissive/free-distillable pipeline.

    Attributes:
        provider_type: ProviderType.STABILITY
        api_key: Stability AI API key
        timeout: Request timeout in seconds

    Available Models:
        - stability-ai/sd3.5-large: SD3.5 Large (distillation-permissive)

    Examples:
        >>> provider = StabilityProvider(api_key="sk-...")
        >>> response = await provider.generate_image(
        ...     prompt="A photorealistic landscape",
        ...     model="stability-ai/sd3.5-large",
        ...     aspect_ratio="16:9"
        ... )
    """

    provider_type = ProviderType.STABILITY

    DEFAULT_TIMEOUT = 120  # Image generation can take a while

    def __init__(self, api_key: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        """Initialize Stability AI provider.

        Args:
            api_key: Stability AI API key (STABILITY_API_KEY).
            timeout: Request timeout in seconds (default: 120).
        """
        super().__init__(api_key)
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get httpx async client (lazy initialization)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json",
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
            AuthenticationError: For 401/403 errors.
            RateLimitError: For 429 errors.
            ProviderError: For other errors.
        """
        if response.status_code in (401, 403):
            raise AuthenticationError(ProviderType.STABILITY)
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                ProviderType.STABILITY,
                retry_after=int(retry_after) if retry_after else None,
            )
        else:
            try:
                error_data = response.json()
                message = error_data.get("message", response.text)
            except Exception:
                message = response.text

            raise ProviderError(
                message=f"Stability AI error: {message}",
                provider=ProviderType.STABILITY,
                status_code=response.status_code,
                retryable=response.status_code >= 500,
            )

    async def call_text(
        self,
        prompt: str,
        model: str,
        response_model: type[T] | None = None,
        **kwargs: Any,
    ) -> LLMResponse[T] | LLMResponse[str]:
        """Text generation is not supported by Stability AI.

        Raises:
            ProviderError: Always, as Stability AI is image-only.
        """
        raise ProviderError(
            message="Stability AI does not support text generation",
            provider=ProviderType.STABILITY,
            retryable=False,
        )

    async def generate_image(
        self,
        prompt: str,
        model: str,
        **kwargs: Any,
    ) -> LLMResponse[str]:
        """Generate an image using Stability AI SD3.5 API.

        Sends a multipart/form-data request to the Stability AI REST API
        and returns the generated image as base64-encoded PNG data.

        Args:
            prompt: The image generation prompt.
            model: Model ID (e.g., "stability-ai/sd3.5-large").
            **kwargs: Additional parameters:
                - aspect_ratio: Image aspect ratio ("1:1", "16:9", "3:2", etc.)
                - output_format: Output format ("png", "jpeg", "webp")
                - negative_prompt: Negative prompt for things to avoid

        Returns:
            LLMResponse containing base64-encoded image data.

        Raises:
            AuthenticationError: If API key is invalid.
            RateLimitError: If rate limit is hit.
            ProviderError: If the API call fails.

        Examples:
            >>> response = await provider.generate_image(
            ...     prompt="A sunset over mountains",
            ...     model="stability-ai/sd3.5-large",
            ...     aspect_ratio="16:9"
            ... )
        """
        start_time = time.perf_counter()

        # Map our model ID to Stability API model parameter
        api_model = STABILITY_MODEL_MAP.get(model, "sd3.5-large")

        # Build multipart form data
        aspect_ratio = kwargs.get("aspect_ratio", DEFAULT_ASPECT_RATIO)
        output_format = kwargs.get("output_format", DEFAULT_OUTPUT_FORMAT)

        form_data = {
            "prompt": prompt,
            "model": api_model,
            "output_format": output_format,
            "aspect_ratio": aspect_ratio,
        }

        # Add optional negative prompt
        if "negative_prompt" in kwargs:
            form_data["negative_prompt"] = kwargs["negative_prompt"]

        logger.debug(
            f"Calling Stability AI: model={api_model}, "
            f"aspect_ratio={aspect_ratio}, format={output_format}"
        )

        try:
            response = await self.client.post(
                STABILITY_SD3_ENDPOINT,
                data=form_data,
            )

            if response.status_code != 200:
                self._handle_error(response)

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Parse JSON response containing base64 image
            data = response.json()
            image_b64 = data.get("image")

            if not image_b64:
                raise ProviderError(
                    message=f"No image in Stability AI response: {str(data)[:500]}",
                    provider=ProviderType.STABILITY,
                    retryable=False,
                )

            logger.info(
                f"Stability AI image generated in {latency_ms}ms "
                f"(model={api_model}, format={output_format})"
            )

            return LLMResponse(
                content=image_b64,
                model=model,
                provider=self.provider_type,
                latency_ms=latency_ms,
                metadata={
                    "mime_type": f"image/{output_format}",
                    "aspect_ratio": aspect_ratio,
                },
            )

        except httpx.HTTPError as e:
            logger.error(f"Stability AI HTTP error: {e}")
            raise ProviderError(
                message=str(e),
                provider=ProviderType.STABILITY,
                retryable=True,
            ) from e

    async def analyze_image(
        self,
        image: str,
        prompt: str,
        model: str,
        **kwargs: Any,
    ) -> LLMResponse[dict[str, Any]]:
        """Image analysis is not supported by Stability AI.

        Raises:
            ProviderError: Always, as Stability AI is generation-only.
        """
        raise ProviderError(
            message="Stability AI does not support image analysis",
            provider=ProviderType.STABILITY,
            retryable=False,
        )

    async def health_check(self) -> bool:
        """Check if Stability AI provider is accessible.

        Makes a minimal request to verify the API key is valid.
        We use a very short prompt to minimize credit usage.

        Returns:
            bool: True if provider is healthy.
        """
        try:
            # Just check that auth works by making a small request
            # We'll catch errors - any non-auth error means the API is reachable
            response = await self.client.post(
                STABILITY_SD3_ENDPOINT,
                data={
                    "prompt": "test",
                    "model": "sd3.5-large",
                    "output_format": "png",
                },
            )
            # 200 = works, 402 = payment required (but API is reachable)
            # Only 401/403 means unhealthy
            return response.status_code not in (401, 403)
        except Exception as e:
            logger.warning(f"Stability AI health check failed: {e}")
            return False
