"""Unit tests for provider abstraction layer.

Tests for app/core/providers.py and provider implementations.

Run with:
    pytest tests/unit/test_providers.py -v
    pytest tests/unit/test_providers.py -v -m fast
"""

import pytest

from app.config import ProviderType
from app.core.providers import (
    AuthenticationError,
    LLMResponse,
    ModelCapability,
    ProviderConfig,
    ProviderError,
    RateLimitError,
)


@pytest.mark.fast
class TestModelCapability:
    """Tests for ModelCapability enum."""

    def test_capability_values(self):
        """Test ModelCapability enum has expected values."""
        assert ModelCapability.TEXT.value == "text"
        assert ModelCapability.IMAGE.value == "image"
        assert ModelCapability.VISION.value == "vision"
        assert ModelCapability.CODE.value == "code"

    def test_capability_is_string_enum(self):
        """Test ModelCapability is a string enum."""
        assert isinstance(ModelCapability.TEXT.value, str)


@pytest.mark.fast
class TestProviderConfig:
    """Tests for ProviderConfig class."""

    def test_provider_config_creation(self, provider_config):
        """Test ProviderConfig can be created with valid data."""
        assert provider_config.primary == ProviderType.GOOGLE
        assert provider_config.fallback == ProviderType.OPENROUTER

    def test_provider_config_default_capabilities(self):
        """Test ProviderConfig has default capabilities."""
        config = ProviderConfig(primary=ProviderType.GOOGLE)
        assert ModelCapability.TEXT in config.capabilities
        assert ModelCapability.IMAGE in config.capabilities

    def test_provider_config_get_model(self, provider_config):
        """Test get_model returns correct model for capability."""
        model = provider_config.get_model(ModelCapability.TEXT)
        assert model == "gemini-3-pro-preview"

    def test_provider_config_get_model_missing(self):
        """Test get_model raises KeyError for missing capability."""
        config = ProviderConfig(
            primary=ProviderType.GOOGLE,
            capabilities={},
        )
        with pytest.raises(KeyError, match="No model configured"):
            config.get_model(ModelCapability.TEXT)

    def test_provider_config_max_retries_validation(self):
        """Test max_retries validation."""
        # Valid range
        config = ProviderConfig(primary=ProviderType.GOOGLE, max_retries=5)
        assert config.max_retries == 5

        # Too low
        with pytest.raises(ValueError):
            ProviderConfig(primary=ProviderType.GOOGLE, max_retries=0)

        # Too high
        with pytest.raises(ValueError):
            ProviderConfig(primary=ProviderType.GOOGLE, max_retries=11)

    def test_provider_config_timeout_validation(self):
        """Test timeout validation."""
        config = ProviderConfig(primary=ProviderType.GOOGLE, timeout=30.0)
        assert config.timeout == 30.0

        with pytest.raises(ValueError):
            ProviderConfig(primary=ProviderType.GOOGLE, timeout=0)


@pytest.mark.fast
class TestLLMResponse:
    """Tests for LLMResponse class."""

    def test_llm_response_creation(self, mock_llm_response):
        """Test LLMResponse can be created."""
        assert mock_llm_response.content == "This is a mock response"
        assert mock_llm_response.model == "gemini-3-pro-preview"
        assert mock_llm_response.provider == ProviderType.GOOGLE

    def test_llm_response_usage(self, mock_llm_response):
        """Test LLMResponse usage tracking."""
        assert mock_llm_response.usage["input_tokens"] == 10
        assert mock_llm_response.usage["output_tokens"] == 20

    def test_llm_response_latency(self, mock_llm_response):
        """Test LLMResponse latency tracking."""
        assert mock_llm_response.latency_ms == 100

    def test_llm_response_with_structured_content(self, mock_response_model):
        """Test LLMResponse with structured content."""
        content = mock_response_model(answer="42", confidence=0.95)
        response = LLMResponse(
            content=content,
            model="test-model",
            provider=ProviderType.GOOGLE,
        )
        assert response.content.answer == "42"
        assert response.content.confidence == 0.95


@pytest.mark.fast
class TestProviderErrors:
    """Tests for provider error classes."""

    def test_provider_error_creation(self):
        """Test ProviderError can be created."""
        error = ProviderError(
            message="Test error",
            provider=ProviderType.GOOGLE,
            status_code=500,
            retryable=True,
        )
        assert str(error) == "[google] (500) Test error"
        assert error.provider == ProviderType.GOOGLE
        assert error.status_code == 500
        assert error.retryable is True

    def test_provider_error_without_status(self):
        """Test ProviderError without status code."""
        error = ProviderError(
            message="Test error",
            provider=ProviderType.OPENROUTER,
        )
        assert str(error) == "[openrouter] Test error"

    def test_rate_limit_error(self):
        """Test RateLimitError creation."""
        error = RateLimitError(ProviderType.GOOGLE, retry_after=30)
        assert "Rate limit exceeded" in str(error)
        assert "30s" in str(error)
        assert error.status_code == 429
        assert error.retryable is True
        assert error.retry_after == 30

    def test_rate_limit_error_without_retry_after(self):
        """Test RateLimitError without retry_after."""
        error = RateLimitError(ProviderType.OPENROUTER)
        assert "Rate limit exceeded" in str(error)
        assert error.retry_after is None

    def test_authentication_error(self):
        """Test AuthenticationError creation."""
        error = AuthenticationError(ProviderType.GOOGLE)
        assert "Authentication failed" in str(error)
        assert "API key" in str(error)
        assert error.status_code == 401
        assert error.retryable is False


@pytest.mark.fast
class TestGoogleProvider:
    """Tests for Google provider (mocked)."""

    def test_google_provider_type(self, mock_google_provider):
        """Test Google provider has correct type."""
        assert mock_google_provider.provider_type == ProviderType.GOOGLE

    @pytest.mark.asyncio
    async def test_google_provider_call_text(self, mock_google_provider):
        """Test Google provider call_text returns response."""
        response = await mock_google_provider.call_text(
            prompt="Test prompt",
            model="gemini-3-pro-preview",
        )
        assert response.content == "Mock Google response"
        assert response.provider == ProviderType.GOOGLE

    @pytest.mark.asyncio
    async def test_google_provider_generate_image(self, mock_google_provider):
        """Test Google provider generate_image returns response."""
        response = await mock_google_provider.generate_image(
            prompt="Test image prompt",
            model="imagen-3.0-generate-002",
        )
        assert response.content == "base64encodedimage"

    @pytest.mark.asyncio
    async def test_google_provider_health_check(self, mock_google_provider):
        """Test Google provider health check."""
        is_healthy = await mock_google_provider.health_check()
        assert is_healthy is True


@pytest.mark.fast
class TestOpenRouterProvider:
    """Tests for OpenRouter provider (mocked)."""

    def test_openrouter_provider_type(self, mock_openrouter_provider):
        """Test OpenRouter provider has correct type."""
        assert mock_openrouter_provider.provider_type == ProviderType.OPENROUTER

    @pytest.mark.asyncio
    async def test_openrouter_provider_call_text(self, mock_openrouter_provider):
        """Test OpenRouter provider call_text returns response."""
        response = await mock_openrouter_provider.call_text(
            prompt="Test prompt",
            model="anthropic/claude-3.5-sonnet",
        )
        assert response.content == "Mock OpenRouter response"
        assert response.provider == ProviderType.OPENROUTER

    @pytest.mark.asyncio
    async def test_openrouter_provider_health_check(self, mock_openrouter_provider):
        """Test OpenRouter provider health check."""
        is_healthy = await mock_openrouter_provider.health_check()
        assert is_healthy is True
