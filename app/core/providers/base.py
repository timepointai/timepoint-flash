"""Base LLM provider abstraction layer.

This module defines the abstract base class and types for LLM providers.
All provider implementations (Google, OpenRouter) inherit from LLMProvider.

Examples:
    >>> from app.core.providers import LLMProvider, ProviderConfig, ProviderType
    >>> config = ProviderConfig(
    ...     primary=ProviderType.GOOGLE,
    ...     fallback=ProviderType.OPENROUTER,
    ...     capabilities={ModelCapability.TEXT: "gemini-3-pro-preview"}
    ... )

Tests:
    - tests/unit/test_providers.py::test_provider_config_creation
    - tests/unit/test_providers.py::test_model_capability_enum
    - tests/unit/test_providers.py::test_llm_response_model
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

# Re-export ProviderType from config for convenience
from app.config import ProviderType

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "ModelCapability",
    "ProviderConfig",
    "ProviderType",
    "ProviderError",
    "RateLimitError",
    "QuotaExhaustedError",
    "AuthenticationError",
]


class ModelCapability(str, Enum):
    """Model capabilities for task routing.

    Different tasks require different model capabilities:
    - TEXT: Text generation and reasoning
    - IMAGE: Image generation
    - VISION: Image understanding/analysis
    - CODE: Code generation and understanding
    """

    TEXT = "text"
    IMAGE = "image"
    VISION = "vision"
    CODE = "code"


class ProviderConfig(BaseModel):
    """Provider configuration with fallback chain.

    Defines which provider to use as primary, which as fallback,
    and which models to use for each capability.

    Attributes:
        primary: Primary LLM provider
        fallback: Fallback provider when primary fails (optional)
        capabilities: Mapping of capabilities to model IDs
        max_retries: Maximum retry attempts before fallback
        timeout: Request timeout in seconds

    Examples:
        >>> config = ProviderConfig(
        ...     primary=ProviderType.GOOGLE,
        ...     fallback=ProviderType.OPENROUTER,
        ...     capabilities={
        ...         ModelCapability.TEXT: "gemini-3-pro-preview",
        ...         ModelCapability.IMAGE: "imagen-3.0-generate-002",
        ...     }
        ... )
    """

    primary: ProviderType = Field(
        description="Primary LLM provider",
    )
    fallback: ProviderType | None = Field(
        default=None,
        description="Fallback provider when primary fails",
    )
    capabilities: dict[ModelCapability, str] = Field(
        default_factory=lambda: {
            ModelCapability.TEXT: "gemini-3-pro-preview",
            ModelCapability.IMAGE: "imagen-3.0-generate-002",
            ModelCapability.VISION: "gemini-2.5-flash",
            ModelCapability.CODE: "gemini-3-pro-preview",
        },
        description="Mapping of capabilities to model IDs",
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts before fallback",
    )
    timeout: float = Field(
        default=60.0,
        gt=0,
        description="Request timeout in seconds",
    )

    def get_model(self, capability: ModelCapability) -> str:
        """Get model ID for a specific capability.

        Args:
            capability: The capability to get the model for.

        Returns:
            str: The model ID.

        Raises:
            KeyError: If no model is configured for the capability.
        """
        if capability not in self.capabilities:
            raise KeyError(f"No model configured for capability: {capability}")
        return self.capabilities[capability]


# Type variable for structured response models
T = TypeVar("T", bound=BaseModel)


class LLMResponse(BaseModel, Generic[T]):
    """Standardized LLM response wrapper.

    Wraps all LLM responses with metadata for tracking and debugging.

    Attributes:
        content: The parsed response content
        raw_response: Raw response from the provider (optional)
        model: Model ID used for generation
        provider: Provider used for generation
        usage: Token usage statistics
        latency_ms: Response latency in milliseconds

    Examples:
        >>> response = LLMResponse(
        ...     content=MyModel(field="value"),
        ...     model="gemini-3-pro-preview",
        ...     provider=ProviderType.GOOGLE,
        ...     usage={"input_tokens": 100, "output_tokens": 50},
        ...     latency_ms=1234,
        ... )
    """

    content: Any = Field(description="Parsed response content")
    raw_response: str | None = Field(
        default=None,
        description="Raw response from provider",
    )
    model: str = Field(description="Model ID used")
    provider: ProviderType = Field(description="Provider used")
    usage: dict[str, int] = Field(
        default_factory=dict,
        description="Token usage statistics",
    )
    latency_ms: int = Field(
        default=0,
        ge=0,
        description="Response latency in milliseconds",
    )


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All provider implementations must inherit from this class and
    implement the abstract methods for text, image, and vision calls.

    Attributes:
        provider_type: The provider type identifier
        api_key: API key for authentication

    Examples:
        >>> class MyProvider(LLMProvider):
        ...     provider_type = ProviderType.GOOGLE
        ...     async def call_text(self, prompt, model, response_model):
        ...         # Implementation
        ...         pass
    """

    provider_type: ProviderType

    def __init__(self, api_key: str) -> None:
        """Initialize provider with API key.

        Args:
            api_key: API key for authentication.
        """
        self.api_key = api_key

    @abstractmethod
    async def call_text(
        self,
        prompt: str,
        model: str,
        response_model: type[T] | None = None,
        **kwargs: Any,
    ) -> LLMResponse[T] | LLMResponse[str]:
        """Generate text with optional structured output.

        Args:
            prompt: The input prompt.
            model: Model ID to use.
            response_model: Optional Pydantic model for structured output.
            **kwargs: Additional provider-specific parameters.

        Returns:
            LLMResponse containing the generated text or structured output.

        Raises:
            ProviderError: If the API call fails.
        """
        pass

    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        model: str,
        **kwargs: Any,
    ) -> LLMResponse[str]:
        """Generate an image from a prompt.

        Args:
            prompt: The image generation prompt.
            model: Model ID to use.
            **kwargs: Additional provider-specific parameters.

        Returns:
            LLMResponse containing the base64-encoded image.

        Raises:
            ProviderError: If the API call fails.
        """
        pass

    @abstractmethod
    async def analyze_image(
        self,
        image: str,
        prompt: str,
        model: str,
        **kwargs: Any,
    ) -> LLMResponse[dict[str, Any]]:
        """Analyze an image with a prompt.

        Args:
            image: Base64-encoded image or URL.
            prompt: The analysis prompt.
            model: Model ID to use.
            **kwargs: Additional provider-specific parameters.

        Returns:
            LLMResponse containing the analysis results.

        Raises:
            ProviderError: If the API call fails.
        """
        pass

    async def health_check(self) -> bool:
        """Check if the provider is accessible.

        Returns:
            bool: True if the provider is healthy.
        """
        try:
            # Simple text call to verify connectivity
            response = await self.call_text(
                prompt="Say 'ok'",
                model="gemini-2.5-flash",
            )
            return bool(response.content)
        except Exception:
            return False


class ProviderError(Exception):
    """Base exception for provider errors.

    Attributes:
        provider: The provider that raised the error
        message: Error message
        status_code: HTTP status code (if applicable)
        retryable: Whether the error is retryable
    """

    def __init__(
        self,
        message: str,
        provider: ProviderType,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        """Initialize provider error.

        Args:
            message: Error message.
            provider: Provider that raised the error.
            status_code: HTTP status code (optional).
            retryable: Whether the error is retryable.
        """
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable

    def __str__(self) -> str:
        """String representation of the error."""
        parts = [f"[{self.provider.value}]", self.args[0]]
        if self.status_code:
            parts.insert(1, f"({self.status_code})")
        return " ".join(parts)


class RateLimitError(ProviderError):
    """Rate limit exceeded error (temporary, retrying may help)."""

    def __init__(self, provider: ProviderType, retry_after: int | None = None) -> None:
        """Initialize rate limit error.

        Args:
            provider: Provider that raised the error.
            retry_after: Seconds to wait before retrying (optional).
        """
        message = "Rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after}s"
        super().__init__(message, provider, status_code=429, retryable=True)
        self.retry_after = retry_after


class QuotaExhaustedError(ProviderError):
    """Daily quota exhausted error (retrying won't help until quota resets).

    This is different from RateLimitError - quota exhaustion means the daily
    limit has been reached (e.g., limit: 0), and retrying is pointless.
    The caller should immediately fall back to an alternative provider.
    """

    def __init__(self, provider: ProviderType, message: str | None = None) -> None:
        """Initialize quota exhausted error.

        Args:
            provider: Provider that raised the error.
            message: Optional custom message with details.
        """
        default_message = "Daily quota exhausted - fallback to alternative provider"
        super().__init__(
            message or default_message,
            provider,
            status_code=429,
            retryable=False,  # Key difference: NOT retryable
        )


class AuthenticationError(ProviderError):
    """Authentication failed error."""

    def __init__(self, provider: ProviderType) -> None:
        """Initialize authentication error.

        Args:
            provider: Provider that raised the error.
        """
        super().__init__(
            "Authentication failed - check API key",
            provider,
            status_code=401,
            retryable=False,
        )
