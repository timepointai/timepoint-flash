"""Unit tests for configuration module.

Tests for app/config.py - Settings and provider configuration.

Run with:
    pytest tests/unit/test_config.py -v
    pytest tests/unit/test_config.py -v -m fast
"""

import pytest

from app.config import Environment, ProviderType, Settings


@pytest.mark.fast
class TestProviderType:
    """Tests for ProviderType enum."""

    def test_provider_type_values(self):
        """Test ProviderType enum has expected values."""
        assert ProviderType.GOOGLE.value == "google"
        assert ProviderType.OPENROUTER.value == "openrouter"

    def test_provider_type_string_conversion(self):
        """Test ProviderType can be converted to string."""
        assert str(ProviderType.GOOGLE) == "ProviderType.GOOGLE"
        assert ProviderType.GOOGLE.value == "google"


@pytest.mark.fast
class TestEnvironment:
    """Tests for Environment enum."""

    def test_environment_values(self):
        """Test Environment enum has expected values."""
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.STAGING.value == "staging"
        assert Environment.PRODUCTION.value == "production"


@pytest.mark.fast
class TestSettings:
    """Tests for Settings class."""

    def test_settings_with_google_key(self):
        """Test settings with only Google API key."""
        settings = Settings(
            GOOGLE_API_KEY="test-google-key",
            OPENROUTER_API_KEY=None,
        )
        assert settings.GOOGLE_API_KEY == "test-google-key"
        assert settings.OPENROUTER_API_KEY is None

    def test_settings_with_openrouter_key(self):
        """Test settings with only OpenRouter API key."""
        settings = Settings(
            GOOGLE_API_KEY=None,
            OPENROUTER_API_KEY="test-openrouter-key",
        )
        assert settings.GOOGLE_API_KEY is None
        assert settings.OPENROUTER_API_KEY == "test-openrouter-key"

    def test_settings_with_both_keys(self):
        """Test settings with both API keys."""
        settings = Settings(
            GOOGLE_API_KEY="test-google-key",
            OPENROUTER_API_KEY="test-openrouter-key",
        )
        assert settings.GOOGLE_API_KEY == "test-google-key"
        assert settings.OPENROUTER_API_KEY == "test-openrouter-key"

    def test_settings_requires_at_least_one_key(self):
        """Test settings validation requires at least one API key."""
        with pytest.raises(ValueError, match="At least one provider API key"):
            Settings(
                GOOGLE_API_KEY=None,
                OPENROUTER_API_KEY=None,
            )

    def test_settings_default_values(self, test_settings):
        """Test settings default values."""
        assert test_settings.PRIMARY_PROVIDER == ProviderType.GOOGLE
        assert test_settings.FALLBACK_PROVIDER == ProviderType.OPENROUTER
        assert test_settings.DEBUG is True

    def test_settings_database_url_validation_sqlite(self):
        """Test database URL validation accepts SQLite."""
        settings = Settings(
            DATABASE_URL="sqlite+aiosqlite:///./test.db",
            GOOGLE_API_KEY="test-key",
        )
        assert settings.DATABASE_URL.startswith("sqlite")

    def test_settings_database_url_validation_postgresql(self):
        """Test database URL validation accepts PostgreSQL."""
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            GOOGLE_API_KEY="test-key",
        )
        assert settings.DATABASE_URL.startswith("postgresql")

    def test_settings_database_url_validation_invalid(self):
        """Test database URL validation rejects invalid URLs."""
        with pytest.raises(ValueError, match="DATABASE_URL must start with"):
            Settings(
                DATABASE_URL="mysql://user:pass@localhost/db",
                GOOGLE_API_KEY="test-key",
            )

    def test_detected_provider_google(self):
        """Test detected_provider returns Google when available."""
        settings = Settings(
            GOOGLE_API_KEY="test-google-key",
            OPENROUTER_API_KEY=None,
        )
        assert settings.detected_provider == ProviderType.GOOGLE

    def test_detected_provider_openrouter(self):
        """Test detected_provider returns OpenRouter as fallback."""
        settings = Settings(
            GOOGLE_API_KEY=None,
            OPENROUTER_API_KEY="test-openrouter-key",
        )
        assert settings.detected_provider == ProviderType.OPENROUTER

    def test_has_provider_google(self, test_settings):
        """Test has_provider for Google."""
        assert test_settings.has_provider(ProviderType.GOOGLE) is True

    def test_has_provider_openrouter(self, test_settings):
        """Test has_provider for OpenRouter."""
        assert test_settings.has_provider(ProviderType.OPENROUTER) is True

    def test_get_api_key_google(self, test_settings):
        """Test get_api_key for Google."""
        key = test_settings.get_api_key(ProviderType.GOOGLE)
        assert key == "test-google-key"

    def test_get_api_key_openrouter(self, test_settings):
        """Test get_api_key for OpenRouter."""
        key = test_settings.get_api_key(ProviderType.OPENROUTER)
        assert key == "test-openrouter-key"

    def test_get_api_key_not_configured(self):
        """Test get_api_key raises for unconfigured provider."""
        settings = Settings(
            GOOGLE_API_KEY=None,
            OPENROUTER_API_KEY="test-key",
        )
        with pytest.raises(ValueError, match="GOOGLE_API_KEY not configured"):
            settings.get_api_key(ProviderType.GOOGLE)

    def test_is_production(self):
        """Test is_production property."""
        dev_settings = Settings(
            ENVIRONMENT=Environment.DEVELOPMENT,
            GOOGLE_API_KEY="test-key",
        )
        assert dev_settings.is_production is False

        prod_settings = Settings(
            ENVIRONMENT=Environment.PRODUCTION,
            GOOGLE_API_KEY="test-key",
        )
        assert prod_settings.is_production is True

    def test_is_sqlite(self):
        """Test is_sqlite property."""
        sqlite_settings = Settings(
            DATABASE_URL="sqlite+aiosqlite:///./test.db",
            GOOGLE_API_KEY="test-key",
        )
        assert sqlite_settings.is_sqlite is True

        pg_settings = Settings(
            DATABASE_URL="postgresql+asyncpg://localhost/db",
            GOOGLE_API_KEY="test-key",
        )
        assert pg_settings.is_sqlite is False

    def test_get_model_config(self, test_settings):
        """Test get_model_config returns model configuration."""
        config = test_settings.get_model_config()
        assert "judge" in config
        assert "creative" in config
        assert "image" in config
