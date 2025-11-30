"""Application configuration with Pydantic Settings.

This module provides centralized configuration management using pydantic-settings.
Settings are loaded from environment variables and .env files.

Examples:
    >>> from app.config import settings
    >>> settings.PRIMARY_PROVIDER
    <ProviderType.GOOGLE: 'google'>

    >>> settings.get_provider_config()
    ProviderConfig(primary=<ProviderType.GOOGLE>, fallback=<ProviderType.OPENROUTER>, ...)

Tests:
    - tests/unit/test_config.py::test_settings_defaults
    - tests/unit/test_config.py::test_provider_detection
    - tests/unit/test_config.py::test_database_url_parsing
"""

from enum import Enum
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderType(str, Enum):
    """Supported LLM providers."""

    GOOGLE = "google"
    OPENROUTER = "openrouter"


class Environment(str, Enum):
    """Application environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Application settings with provider configuration.

    Settings are loaded from environment variables and .env file.
    At least one provider API key (GOOGLE_API_KEY or OPENROUTER_API_KEY) is required.

    Attributes:
        DATABASE_URL: Database connection string (SQLite or PostgreSQL)
        GOOGLE_API_KEY: Google AI API key for Gemini models
        OPENROUTER_API_KEY: OpenRouter API key for multi-model access
        PRIMARY_PROVIDER: Primary LLM provider (google or openrouter)
        FALLBACK_PROVIDER: Fallback provider when primary fails
        JUDGE_MODEL: Model for fast validation/judging tasks
        CREATIVE_MODEL: Model for complex creative generation
        IMAGE_MODEL: Model for image generation
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./timepoint.db",
        description="Database connection string",
    )

    # Provider API Keys
    GOOGLE_API_KEY: str | None = Field(
        default=None,
        description="Google AI API key",
    )
    OPENROUTER_API_KEY: str | None = Field(
        default=None,
        description="OpenRouter API key",
    )

    # Provider Selection
    PRIMARY_PROVIDER: ProviderType = Field(
        default=ProviderType.GOOGLE,
        description="Primary LLM provider",
    )
    FALLBACK_PROVIDER: ProviderType | None = Field(
        default=ProviderType.OPENROUTER,
        description="Fallback provider when primary fails",
    )

    # Model Selection
    JUDGE_MODEL: str = Field(
        default="gemini-2.5-flash",
        description="Model for validation/judging (fast)",
    )
    CREATIVE_MODEL: str = Field(
        default="gemini-3-pro-preview",
        description="Model for creative generation (quality)",
    )
    IMAGE_MODEL: str = Field(
        default="google/gemini-3-pro-image-preview",
        description="Model for image generation",
    )

    # Observability
    LOGFIRE_TOKEN: str | None = Field(
        default=None,
        description="Logfire token for monitoring",
    )

    # Application Settings
    ENVIRONMENT: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Application environment",
    )
    DEBUG: bool = Field(
        default=True,
        description="Enable debug mode",
    )
    RATE_LIMIT: int = Field(
        default=60,
        description="API rate limit (requests per minute)",
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format."""
        valid_prefixes = ("sqlite", "postgresql", "postgres")
        if not any(v.startswith(prefix) for prefix in valid_prefixes):
            raise ValueError(
                f"DATABASE_URL must start with one of: {valid_prefixes}"
            )
        return v

    @model_validator(mode="after")
    def validate_providers(self) -> "Settings":
        """Ensure at least one provider API key is configured."""
        if not self.GOOGLE_API_KEY and not self.OPENROUTER_API_KEY:
            raise ValueError(
                "At least one provider API key is required "
                "(GOOGLE_API_KEY or OPENROUTER_API_KEY)"
            )
        return self

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT == Environment.PRODUCTION

    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite database."""
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def detected_provider(self) -> ProviderType:
        """Auto-detect primary provider based on available API keys.

        Returns:
            ProviderType: The detected provider based on API key availability.

        Raises:
            ValueError: If no API keys are configured.
        """
        if self.GOOGLE_API_KEY:
            return ProviderType.GOOGLE
        elif self.OPENROUTER_API_KEY:
            return ProviderType.OPENROUTER
        raise ValueError("No API keys configured")

    def has_provider(self, provider: ProviderType) -> bool:
        """Check if a specific provider is configured.

        Args:
            provider: The provider to check.

        Returns:
            bool: True if the provider's API key is configured.
        """
        if provider == ProviderType.GOOGLE:
            return bool(self.GOOGLE_API_KEY)
        elif provider == ProviderType.OPENROUTER:
            return bool(self.OPENROUTER_API_KEY)
        return False

    def get_api_key(self, provider: ProviderType) -> str:
        """Get API key for a specific provider.

        Args:
            provider: The provider to get the key for.

        Returns:
            str: The API key.

        Raises:
            ValueError: If the provider's API key is not configured.
        """
        if provider == ProviderType.GOOGLE:
            if not self.GOOGLE_API_KEY:
                raise ValueError("GOOGLE_API_KEY not configured")
            return self.GOOGLE_API_KEY
        elif provider == ProviderType.OPENROUTER:
            if not self.OPENROUTER_API_KEY:
                raise ValueError("OPENROUTER_API_KEY not configured")
            return self.OPENROUTER_API_KEY
        raise ValueError(f"Unknown provider: {provider}")

    def get_model_config(self) -> dict[str, Any]:
        """Get model configuration dictionary.

        Returns:
            dict: Model configuration with judge, creative, and image models.
        """
        return {
            "judge": self.JUDGE_MODEL,
            "creative": self.CREATIVE_MODEL,
            "image": self.IMAGE_MODEL,
        }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Settings: The application settings.

    Examples:
        >>> settings = get_settings()
        >>> settings.PRIMARY_PROVIDER
        <ProviderType.GOOGLE: 'google'>
    """
    return Settings()


# Global settings instance for convenience
settings = get_settings()
