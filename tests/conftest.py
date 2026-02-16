"""Pytest configuration and fixtures for TIMEPOINT Flash.

This module provides shared fixtures, markers, and test utilities.
All fixtures are available to all test modules.

Markers:
    fast: Fast unit tests (no API calls, <1s each)
    integration: Integration tests (may use mocked APIs)
    e2e: End-to-end tests (requires real API keys)
    requires_api: Tests that require API keys

Usage:
    pytest -m fast          # Run only fast tests
    pytest -m integration   # Run integration tests
    pytest -m e2e          # Run e2e tests (slow, needs API keys)
"""

import os
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from pydantic import BaseModel

# Set test environment before importing app modules
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_timepoint.db")
# Set dummy API keys for tests that don't actually call APIs
os.environ.setdefault("GOOGLE_API_KEY", "test-google-key-for-testing")
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key-for-testing")
# Auth test defaults
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("SHARE_URL_BASE", "https://timepointai.com/t")


# ============================================================================
# Pytest Configuration
# ============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "fast: Fast unit tests (no API calls)")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests (requires API keys)")
    config.addinivalue_line("markers", "requires_api: Tests requiring API keys")


# ============================================================================
# Config Fixtures
# ============================================================================


@pytest.fixture
def test_settings():
    """Get test settings instance."""
    from app.config import Settings

    return Settings(
        DATABASE_URL="sqlite+aiosqlite:///./test_timepoint.db",
        GOOGLE_API_KEY="test-google-key",
        OPENROUTER_API_KEY="test-openrouter-key",
        DEBUG=True,
        SHARE_URL_BASE="https://timepointai.com/t",
    )


@pytest.fixture
def provider_config():
    """Create test provider configuration."""
    from app.config import ProviderType
    from app.core.providers import ModelCapability, ProviderConfig

    return ProviderConfig(
        primary=ProviderType.GOOGLE,
        fallback=ProviderType.OPENROUTER,
        capabilities={
            ModelCapability.TEXT: "gemini-3-pro-preview",
            ModelCapability.IMAGE: "imagen-3.0-generate-002",
            ModelCapability.VISION: "gemini-2.5-flash",
            ModelCapability.CODE: "gemini-3-pro-preview",
        },
    )


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def test_db():
    """Create test database and clean up after."""
    from app.database import close_db, drop_db, get_engine, init_db

    # Initialize test database
    await init_db()

    yield

    # Cleanup
    await drop_db()
    await close_db()


@pytest_asyncio.fixture
async def db_session(test_db):
    """Get database session for tests."""
    from app.database import get_session

    async with get_session() as session:
        yield session


# ============================================================================
# Model Fixtures
# ============================================================================


@pytest.fixture
def sample_timepoint_data() -> dict[str, Any]:
    """Sample timepoint data for testing."""
    return {
        "query": "signing of the declaration of independence",
        "slug": "signing-declaration-independence-1776",
        "year": 1776,
        "month": 7,
        "day": 4,
        "season": "summer",
        "time_of_day": "afternoon",
        "location": "Independence Hall, Philadelphia",
        "metadata_json": {
            "historical_period": "American Revolution",
            "significance": "Declaration signing",
        },
        "character_data_json": {
            "characters": [
                {"name": "John Hancock", "role": "President of Congress"},
                {"name": "Benjamin Franklin", "role": "Delegate"},
            ]
        },
        "scene_data_json": {
            "environment": "Grand assembly hall",
            "lighting": "Natural daylight through windows",
        },
        "dialog_json": [
            {"speaker": "John Hancock", "line": "We must all hang together..."},
        ],
    }


@pytest_asyncio.fixture
async def sample_timepoint(db_session, sample_timepoint_data):
    """Create and return a sample timepoint in the database."""
    from app.models import Timepoint, TimepointStatus

    timepoint = Timepoint.create(**sample_timepoint_data)
    timepoint.status = TimepointStatus.COMPLETED
    db_session.add(timepoint)
    await db_session.commit()
    await db_session.refresh(timepoint)
    return timepoint


# ============================================================================
# Provider Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response."""
    from app.config import ProviderType
    from app.core.providers import LLMResponse

    return LLMResponse(
        content="This is a mock response",
        raw_response="This is a mock response",
        model="gemini-3-pro-preview",
        provider=ProviderType.GOOGLE,
        usage={"input_tokens": 10, "output_tokens": 20},
        latency_ms=100,
    )


@pytest.fixture
def mock_google_provider():
    """Create a mocked Google provider."""
    from app.config import ProviderType
    from app.core.providers import LLMResponse

    mock = AsyncMock()
    mock.provider_type = ProviderType.GOOGLE
    mock.call_text = AsyncMock(
        return_value=LLMResponse(
            content="Mock Google response",
            model="gemini-3-pro-preview",
            provider=ProviderType.GOOGLE,
            usage={"input_tokens": 10, "output_tokens": 20},
            latency_ms=100,
        )
    )
    mock.generate_image = AsyncMock(
        return_value=LLMResponse(
            content="base64encodedimage",
            model="imagen-3.0-generate-002",
            provider=ProviderType.GOOGLE,
            latency_ms=500,
        )
    )
    mock.analyze_image = AsyncMock(
        return_value=LLMResponse(
            content={"analysis": "Mock analysis"},
            model="gemini-2.5-flash",
            provider=ProviderType.GOOGLE,
            usage={"input_tokens": 100, "output_tokens": 50},
            latency_ms=200,
        )
    )
    mock.health_check = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_openrouter_provider():
    """Create a mocked OpenRouter provider."""
    from app.config import ProviderType
    from app.core.providers import LLMResponse

    mock = AsyncMock()
    mock.provider_type = ProviderType.OPENROUTER
    mock.call_text = AsyncMock(
        return_value=LLMResponse(
            content="Mock OpenRouter response",
            model="anthropic/claude-3.5-sonnet",
            provider=ProviderType.OPENROUTER,
            usage={"input_tokens": 15, "output_tokens": 25},
            latency_ms=150,
        )
    )
    mock.generate_image = AsyncMock(
        return_value=LLMResponse(
            content="base64encodedimage",
            model="google/gemini-3-pro-image-preview",
            provider=ProviderType.OPENROUTER,
            latency_ms=600,
        )
    )
    mock.analyze_image = AsyncMock(
        return_value=LLMResponse(
            content={"analysis": "Mock OpenRouter analysis"},
            model="anthropic/claude-3.5-sonnet",
            provider=ProviderType.OPENROUTER,
            usage={"input_tokens": 120, "output_tokens": 60},
            latency_ms=250,
        )
    )
    mock.health_check = AsyncMock(return_value=True)
    mock.close = AsyncMock()
    return mock


# ============================================================================
# HTTP Client Fixtures
# ============================================================================


@pytest.fixture
def mock_httpx_client():
    """Create a mocked httpx AsyncClient."""
    mock = AsyncMock()
    mock.is_closed = False

    # Mock successful response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Mock response"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }

    mock.post = AsyncMock(return_value=mock_response)
    mock.get = AsyncMock(return_value=mock_response)
    mock.aclose = AsyncMock()

    return mock


# ============================================================================
# FastAPI Test Client Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def test_client():
    """Get async test client for FastAPI app."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


# ============================================================================
# Pydantic Model Fixtures
# ============================================================================


class MockResponseModel(BaseModel):
    """Mock Pydantic model for testing structured outputs."""

    answer: str
    confidence: float = 1.0


@pytest.fixture
def mock_response_model():
    """Get mock response model class."""
    return MockResponseModel


# ============================================================================
# Utility Fixtures
# ============================================================================


@pytest.fixture
def cleanup_test_files():
    """Cleanup test files after test."""
    files_to_cleanup = []

    yield files_to_cleanup

    import os

    for filepath in files_to_cleanup:
        if os.path.exists(filepath):
            os.remove(filepath)


# ============================================================================
# E2E Fixtures (Real API calls)
# ============================================================================


@pytest.fixture
def real_settings():
    """Get settings with real API keys from environment/.env.

    Unlike test_settings, this uses actual API keys for e2e testing.
    Will skip test if no real API keys are configured.
    """
    from dotenv import load_dotenv

    from app.config import Settings

    # Force reload of .env file to get real keys (not the test defaults set at import time)
    load_dotenv(override=True)

    # Clear the lru_cache to force fresh settings load
    from app.config import get_settings
    get_settings.cache_clear()

    settings = Settings()

    # Skip if using dummy test keys
    if settings.GOOGLE_API_KEY and settings.GOOGLE_API_KEY.startswith("test-"):
        pytest.skip("Real GOOGLE_API_KEY required for e2e tests")
    if not settings.GOOGLE_API_KEY and not settings.OPENROUTER_API_KEY:
        pytest.skip("No real API keys configured for e2e tests")

    return settings


@pytest_asyncio.fixture
async def real_router(real_settings):
    """Get real LLM router for e2e tests.

    Uses actual API keys to make real LLM calls.
    Automatically closes router after test.
    """
    from app.core.llm_router import LLMRouter

    router = LLMRouter()
    yield router
    await router.close()


@pytest_asyncio.fixture
async def real_google_provider(real_settings):
    """Get real Google provider for e2e tests.

    Creates a GoogleProvider with actual API key.
    Skips if Google API key not configured.
    """
    from app.core.providers.google import GoogleProvider

    if not real_settings.GOOGLE_API_KEY:
        pytest.skip("GOOGLE_API_KEY not configured")

    provider = GoogleProvider(api_key=real_settings.GOOGLE_API_KEY)
    yield provider


@pytest_asyncio.fixture
async def real_openrouter_provider(real_settings):
    """Get real OpenRouter provider for e2e tests.

    Creates an OpenRouterProvider with actual API key.
    Skips if OpenRouter API key not configured.
    """
    from app.core.providers.openrouter import OpenRouterProvider

    if not real_settings.OPENROUTER_API_KEY:
        pytest.skip("OPENROUTER_API_KEY not configured")

    provider = OpenRouterProvider(api_key=real_settings.OPENROUTER_API_KEY)
    yield provider
    await provider.close()


@pytest_asyncio.fixture
async def e2e_test_db():
    """Create e2e test database with cleanup.

    Similar to test_db but specifically for e2e tests.
    Uses a separate database file to avoid conflicts.
    """
    from app.database import close_db, drop_db, init_db

    # Use a separate e2e test database
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./e2e_test_timepoint.db"

    await init_db()
    yield
    await drop_db()
    await close_db()

    # Clean up the database file
    if os.path.exists("./e2e_test_timepoint.db"):
        os.remove("./e2e_test_timepoint.db")
