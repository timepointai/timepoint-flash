"""LLM Provider abstraction and implementations.

Re-exports base classes and provider implementations for convenient imports.
"""

# Base classes (import from base module)
from app.core.providers.base import (
    AuthenticationError,
    LLMProvider,
    LLMResponse,
    ModelCapability,
    ProviderConfig,
    ProviderError,
    ProviderType,
    QuotaExhaustedError,
    RateLimitError,
)

# Provider implementations - lazy imports to avoid circular issues
from app.core.providers.google import GoogleProvider
from app.core.providers.openrouter import OpenRouterProvider

__all__ = [
    # Base classes
    "AuthenticationError",
    "LLMProvider",
    "LLMResponse",
    "ModelCapability",
    "ProviderConfig",
    "ProviderError",
    "ProviderType",
    "QuotaExhaustedError",
    "RateLimitError",
    # Implementations
    "GoogleProvider",
    "OpenRouterProvider",
]
