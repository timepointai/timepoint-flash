"""Google Gen AI SDK provider implementation.

This module provides integration with Google's Gemini models via the Gen AI SDK.
Supports text generation, image generation, and vision capabilities.

Examples:
    >>> from app.core.providers.google import GoogleProvider
    >>> provider = GoogleProvider(api_key="your-api-key")
    >>> response = await provider.call_text(
    ...     prompt="Explain quantum computing",
    ...     model="gemini-3-pro-preview"
    ... )
    >>> print(response.content)

Tests:
    - tests/unit/test_providers.py::test_google_provider_init
    - tests/unit/test_providers.py::test_google_provider_call_text
    - tests/integration/test_llm_router.py::test_google_provider_integration
"""

import base64
import logging
import time
from typing import Any, TypeVar

from pydantic import BaseModel

from app.config import ProviderType

# Import from base module directly to avoid circular import
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

# Lazy import for google.genai to handle missing dependency gracefully
_genai_client = None


def _get_genai_client(api_key: str) -> Any:
    """Get or create Google Gen AI client.

    Args:
        api_key: Google API key.

    Returns:
        Configured Gen AI client.

    Raises:
        ImportError: If google-genai is not installed.
    """
    global _genai_client
    if _genai_client is None:
        try:
            from google import genai
            from google.genai import types

            _genai_client = genai.Client(api_key=api_key)
        except ImportError as e:
            raise ImportError(
                "google-genai is required for Google provider. "
                "Install with: pip install google-genai"
            ) from e
    return _genai_client


class GoogleProvider(LLMProvider):
    """Google Gen AI SDK provider for Gemini models.

    Supports Gemini 3 Pro, Gemini 2.5 Flash, and Imagen 3 models.
    Uses the google-genai SDK (v1.51.0+) for API access.

    Attributes:
        provider_type: ProviderType.GOOGLE
        api_key: Google AI API key
        client: Gen AI client instance

    Available Models:
        - gemini-3-pro-preview: Flagship model for complex reasoning
        - gemini-2.5-flash: Fast model for judging/validation
        - gemini-2.5-pro: Creative generation
        - imagen-3.0-generate-002: Image generation

    Examples:
        >>> provider = GoogleProvider(api_key="AIza...")
        >>> response = await provider.call_text(
        ...     prompt="Write a haiku about coding",
        ...     model="gemini-3-pro-preview"
        ... )
    """

    provider_type = ProviderType.GOOGLE

    def __init__(self, api_key: str) -> None:
        """Initialize Google provider.

        Args:
            api_key: Google AI API key.
        """
        super().__init__(api_key)
        self._client: Any = None  # Lazy initialization

    @property
    def client(self) -> Any:
        """Get Gen AI client (lazy initialization)."""
        if self._client is None:
            self._client = _get_genai_client(self.api_key)
        return self._client

    def _handle_error(self, error: Exception) -> None:
        """Convert Google API errors to provider errors.

        Args:
            error: The original exception.

        Raises:
            AuthenticationError: For 401 errors.
            RateLimitError: For 429 errors.
            ProviderError: For other errors.
        """
        error_str = str(error).lower()

        if "401" in error_str or "invalid api key" in error_str:
            raise AuthenticationError(ProviderType.GOOGLE) from error
        elif "429" in error_str or "rate limit" in error_str:
            raise RateLimitError(ProviderType.GOOGLE) from error
        else:
            raise ProviderError(
                message=str(error),
                provider=ProviderType.GOOGLE,
                retryable="timeout" in error_str or "503" in error_str,
            ) from error

    async def call_text(
        self,
        prompt: str,
        model: str,
        response_model: type[T] | None = None,
        **kwargs: Any,
    ) -> LLMResponse[T] | LLMResponse[str]:
        """Generate text with optional structured output.

        Uses google.genai SDK for generation. Supports both plain text
        and structured output via Pydantic models.

        Args:
            prompt: The input prompt.
            model: Model ID (e.g., "gemini-3-pro-preview").
            response_model: Optional Pydantic model for structured output.
            **kwargs: Additional parameters:
                - thinking_level: Reasoning depth ("none", "low", "medium", "high")
                - temperature: Sampling temperature (0.0-2.0)
                - max_tokens: Maximum output tokens

        Returns:
            LLMResponse containing generated text or structured output.

        Raises:
            ProviderError: If the API call fails.

        Examples:
            >>> response = await provider.call_text(
            ...     prompt="Explain AI",
            ...     model="gemini-3-pro-preview",
            ...     thinking_level="medium"
            ... )
        """
        start_time = time.perf_counter()

        try:
            from google.genai import types

            # Build config
            config_params: dict[str, Any] = {}

            if "temperature" in kwargs:
                config_params["temperature"] = kwargs["temperature"]
            if "max_tokens" in kwargs:
                config_params["max_output_tokens"] = kwargs["max_tokens"]
            if "thinking_level" in kwargs:
                config_params["thinking_config"] = types.ThinkingConfig(
                    thinking_budget=kwargs["thinking_level"]
                )

            # Add response schema if response_model provided
            if response_model is not None:
                config_params["response_mime_type"] = "application/json"
                config_params["response_schema"] = response_model

            config = types.GenerateContentConfig(**config_params) if config_params else None

            # Make API call
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Parse response
            if response_model is not None and response.text:
                import json

                parsed = response_model.model_validate_json(response.text)
                content = parsed
            else:
                content = response.text or ""

            # Extract usage - use `or 0` to handle None values from getattr
            usage: dict[str, int] = {}
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = {
                    "input_tokens": getattr(response.usage_metadata, "prompt_token_count", 0) or 0,
                    "output_tokens": getattr(response.usage_metadata, "candidates_token_count", 0) or 0,
                }

            return LLMResponse(
                content=content,
                raw_response=response.text,
                model=model,
                provider=self.provider_type,
                usage=usage,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(f"Google API error: {e}")
            self._handle_error(e)
            raise  # Should not reach here due to _handle_error raising

    async def generate_image(
        self,
        prompt: str,
        model: str,
        **kwargs: Any,
    ) -> LLMResponse[str]:
        """Generate an image from a prompt.

        Automatically selects the appropriate API based on model:
        - Imagen models (imagen-*): Uses generate_images() API
        - Gemini models (gemini-*-image*): Uses generate_content() with image modality

        Args:
            prompt: The image generation prompt.
            model: Model ID. Supported models:
                - "imagen-3.0-generate-002": Imagen 3 (legacy)
                - "gemini-2.5-flash-image": Nano Banana (fast)
                - "gemini-3-pro-image-preview": Nano Banana Pro (best quality)
            **kwargs: Additional parameters:
                - aspect_ratio: Image aspect ratio ("1:1", "16:9", "3:2", etc.)
                - image_size: For Gemini models ("1K", "2K", "4K")
                - number_of_images: Number of images to generate (1-4)

        Returns:
            LLMResponse containing base64-encoded image.

        Raises:
            ProviderError: If the API call fails.

        Examples:
            >>> response = await provider.generate_image(
            ...     prompt="A sunset over mountains",
            ...     model="gemini-3-pro-image-preview"
            ... )
        """
        # Route to appropriate method based on model type
        if model.startswith("gemini-") and "image" in model.lower():
            return await self._generate_image_gemini(prompt, model, **kwargs)
        else:
            return await self._generate_image_imagen(prompt, model, **kwargs)

    async def _generate_image_gemini(
        self,
        prompt: str,
        model: str,
        **kwargs: Any,
    ) -> LLMResponse[str]:
        """Generate image using Gemini native image models (Nano Banana / Nano Banana Pro).

        Uses generate_content() with response_modalities=['IMAGE'].

        Args:
            prompt: The image generation prompt.
            model: Gemini image model (e.g., "gemini-2.5-flash-image", "gemini-3-pro-image-preview").
            **kwargs: Additional parameters:
                - aspect_ratio: Image aspect ratio ("1:1", "16:9", "3:2", etc.)
                - image_size: Resolution ("1K", "2K", "4K")

        Returns:
            LLMResponse containing base64-encoded image.
        """
        start_time = time.perf_counter()

        try:
            from google.genai import types

            # Build image config
            image_config_params: dict[str, Any] = {}
            if "aspect_ratio" in kwargs:
                image_config_params["aspect_ratio"] = kwargs["aspect_ratio"]
            if "image_size" in kwargs:
                image_config_params["image_size"] = kwargs["image_size"]

            # Build generation config with image output modality
            config_params: dict[str, Any] = {
                "response_modalities": ["IMAGE"],
            }
            if image_config_params:
                config_params["image_config"] = types.ImageConfig(**image_config_params)

            config = types.GenerateContentConfig(**config_params)

            # Make API call
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Extract image from response parts
            image_b64 = None
            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "inline_data") and part.inline_data:
                        image_data = part.inline_data.data
                        image_b64 = base64.b64encode(image_data).decode("utf-8")
                        break

            if not image_b64:
                raise ProviderError(
                    message="No image generated from Gemini model",
                    provider=ProviderType.GOOGLE,
                )

            return LLMResponse(
                content=image_b64,
                model=model,
                provider=self.provider_type,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(f"Gemini image generation error: {e}")
            self._handle_error(e)
            raise

    async def _generate_image_imagen(
        self,
        prompt: str,
        model: str,
        **kwargs: Any,
    ) -> LLMResponse[str]:
        """Generate image using Imagen API (legacy).

        Uses generate_images() for Imagen 3 models.

        Args:
            prompt: The image generation prompt.
            model: Imagen model ID (e.g., "imagen-3.0-generate-002").
            **kwargs: Additional parameters:
                - aspect_ratio: Image aspect ratio ("1:1", "16:9", etc.)
                - number_of_images: Number of images to generate (1-4)

        Returns:
            LLMResponse containing base64-encoded image.
        """
        start_time = time.perf_counter()

        try:
            from google.genai import types

            config_params: dict[str, Any] = {}
            if "aspect_ratio" in kwargs:
                config_params["aspect_ratio"] = kwargs["aspect_ratio"]
            if "number_of_images" in kwargs:
                config_params["number_of_images"] = kwargs["number_of_images"]

            response = await self.client.aio.models.generate_images(
                model=model,
                prompt=prompt,
                config=types.GenerateImagesConfig(**config_params) if config_params else None,
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Extract first image
            if response.generated_images:
                image_data = response.generated_images[0].image.image_bytes
                image_b64 = base64.b64encode(image_data).decode("utf-8")
            else:
                raise ProviderError(
                    message="No image generated",
                    provider=ProviderType.GOOGLE,
                )

            return LLMResponse(
                content=image_b64,
                model=model,
                provider=self.provider_type,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(f"Google Imagen error: {e}")
            self._handle_error(e)
            raise

    async def analyze_image(
        self,
        image: str,
        prompt: str,
        model: str,
        **kwargs: Any,
    ) -> LLMResponse[dict[str, Any]]:
        """Analyze an image with a prompt.

        Uses Gemini's vision capabilities.

        Args:
            image: Base64-encoded image or URL.
            prompt: The analysis prompt.
            model: Model ID (e.g., "gemini-2.5-flash").
            **kwargs: Additional parameters.

        Returns:
            LLMResponse containing analysis results.

        Raises:
            ProviderError: If the API call fails.

        Examples:
            >>> response = await provider.analyze_image(
            ...     image="base64...",
            ...     prompt="Describe this image",
            ...     model="gemini-2.5-flash"
            ... )
        """
        start_time = time.perf_counter()

        try:
            from google.genai import types

            # Determine if image is URL or base64
            if image.startswith(("http://", "https://")):
                image_part = types.Part.from_uri(file_uri=image, mime_type="image/jpeg")
            else:
                # Assume base64
                image_bytes = base64.b64decode(image)
                image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

            # Build contents with image and text
            contents = [
                image_part,
                types.Part.from_text(prompt),
            ]

            response = await self.client.aio.models.generate_content(
                model=model,
                contents=contents,
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Parse response as dict
            import json

            try:
                content = json.loads(response.text) if response.text else {}
            except json.JSONDecodeError:
                content = {"analysis": response.text}

            # Extract usage - use `or 0` to handle None values from getattr
            usage: dict[str, int] = {}
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = {
                    "input_tokens": getattr(response.usage_metadata, "prompt_token_count", 0) or 0,
                    "output_tokens": getattr(response.usage_metadata, "candidates_token_count", 0) or 0,
                }

            return LLMResponse(
                content=content,
                raw_response=response.text,
                model=model,
                provider=self.provider_type,
                usage=usage,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(f"Google vision error: {e}")
            self._handle_error(e)
            raise

    async def health_check(self) -> bool:
        """Check if Google provider is accessible.

        Makes a minimal API call to verify connectivity.
        Note: gemini-2.5-flash may return empty text for simple prompts,
        so we just verify the API responds without error.

        Returns:
            bool: True if provider is healthy.
        """
        try:
            # Make a minimal API call - we just need to verify connectivity
            # gemini-2.5-flash may return empty text, but that's OK for health check
            from google.genai import types

            response = await self.client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents="ping",
                config=types.GenerateContentConfig(max_output_tokens=10),
            )
            # If we get here without exception, the API is accessible
            return True
        except Exception as e:
            logger.warning(f"Google health check failed: {e}")
            return False
