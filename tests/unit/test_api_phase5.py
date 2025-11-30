"""Tests for Phase 5 API endpoints.

Tests:
    - Streaming endpoint models
    - Delete endpoint models
    - Temporal navigation models
    - Model discovery endpoints
"""

import pytest
from pydantic import ValidationError

from app.api.v1.timepoints import (
    DeleteResponse,
    GenerateRequest,
    StreamEvent,
)
from app.api.v1.temporal import (
    NavigationRequest,
    NavigationResponse,
)
from app.api.v1.models import (
    ModelInfo,
    ModelListResponse,
    ProviderStatus,
    ProvidersResponse,
    get_configured_models,
)


# GenerateRequest Tests


@pytest.mark.fast
class TestGenerateRequest:
    """Tests for GenerateRequest model."""

    def test_valid_request(self):
        """Test creating a valid generate request."""
        request = GenerateRequest(query="signing of the declaration")
        assert request.query == "signing of the declaration"
        assert request.generate_image is False

    def test_request_with_image(self):
        """Test request with image generation enabled."""
        request = GenerateRequest(
            query="rome 50 BCE",
            generate_image=True,
        )
        assert request.generate_image is True

    def test_query_min_length(self):
        """Test query minimum length validation."""
        with pytest.raises(ValidationError):
            GenerateRequest(query="ab")

    def test_query_max_length(self):
        """Test query maximum length validation."""
        with pytest.raises(ValidationError):
            GenerateRequest(query="a" * 501)


# StreamEvent Tests


@pytest.mark.fast
class TestStreamEvent:
    """Tests for StreamEvent model."""

    def test_start_event(self):
        """Test creating a start event."""
        event = StreamEvent(
            event="start",
            step="initialization",
            data={"query": "test"},
            progress=0,
        )
        assert event.event == "start"
        assert event.progress == 0

    def test_complete_event(self):
        """Test creating a complete event."""
        event = StreamEvent(
            event="step_complete",
            step="judge",
            data={"latency_ms": 100},
            progress=10,
        )
        assert event.step == "judge"
        assert event.progress == 10

    def test_error_event(self):
        """Test creating an error event."""
        event = StreamEvent(
            event="error",
            error="API timeout",
            progress=0,
        )
        assert event.error == "API timeout"

    def test_event_serialization(self):
        """Test event JSON serialization."""
        event = StreamEvent(
            event="done",
            step="complete",
            data={"timepoint_id": "abc123"},
            progress=100,
        )
        json_str = event.model_dump_json()
        assert "done" in json_str
        assert "abc123" in json_str


# DeleteResponse Tests


@pytest.mark.fast
class TestDeleteResponse:
    """Tests for DeleteResponse model."""

    def test_successful_delete(self):
        """Test successful delete response."""
        response = DeleteResponse(
            id="abc123",
            deleted=True,
            message="Timepoint deleted successfully",
        )
        assert response.deleted is True

    def test_failed_delete(self):
        """Test failed delete response."""
        response = DeleteResponse(
            id="abc123",
            deleted=False,
            message="Timepoint not found",
        )
        assert response.deleted is False


# NavigationRequest Tests


@pytest.mark.fast
class TestNavigationRequest:
    """Tests for NavigationRequest model."""

    def test_default_values(self):
        """Test default navigation values."""
        request = NavigationRequest()
        assert request.units == 1
        assert request.unit == "day"

    def test_custom_values(self):
        """Test custom navigation values."""
        request = NavigationRequest(units=10, unit="year")
        assert request.units == 10
        assert request.unit == "year"

    def test_units_bounds(self):
        """Test units bounds validation."""
        # Valid bounds
        NavigationRequest(units=1)
        NavigationRequest(units=365)

        # Invalid bounds
        with pytest.raises(ValidationError):
            NavigationRequest(units=0)
        with pytest.raises(ValidationError):
            NavigationRequest(units=366)


# NavigationResponse Tests


@pytest.mark.fast
class TestNavigationResponse:
    """Tests for NavigationResponse model."""

    def test_navigation_response(self):
        """Test creating navigation response."""
        response = NavigationResponse(
            source_id="abc123",
            target_id="def456",
            source_year=1776,
            target_year=1777,
            direction="next",
            units=1,
            unit="year",
            message="Generated 1 year forward",
        )
        assert response.source_year == 1776
        assert response.target_year == 1777
        assert response.direction == "next"


# ModelInfo Tests


@pytest.mark.fast
class TestModelInfo:
    """Tests for ModelInfo model."""

    def test_basic_model_info(self):
        """Test creating basic model info."""
        model = ModelInfo(
            id="gemini-3-pro-preview",
            name="Gemini 3 Pro Preview",
            provider="google",
        )
        assert model.id == "gemini-3-pro-preview"
        assert model.provider == "google"
        assert model.is_available is True

    def test_model_with_capabilities(self):
        """Test model with capabilities."""
        model = ModelInfo(
            id="gpt-4o",
            name="GPT-4o",
            provider="openrouter",
            capabilities=["text", "vision"],
            context_length=128000,
        )
        assert "text" in model.capabilities
        assert "vision" in model.capabilities
        assert model.context_length == 128000

    def test_model_with_pricing(self):
        """Test model with pricing."""
        model = ModelInfo(
            id="claude-3.5-sonnet",
            name="Claude 3.5 Sonnet",
            provider="openrouter",
            pricing={"prompt": 0.000003, "completion": 0.000015},
        )
        assert model.pricing["prompt"] == 0.000003


# ModelListResponse Tests


@pytest.mark.fast
class TestModelListResponse:
    """Tests for ModelListResponse model."""

    def test_model_list_response(self):
        """Test creating model list response."""
        models = [
            ModelInfo(id="model1", name="Model 1", provider="google"),
            ModelInfo(id="model2", name="Model 2", provider="openrouter"),
        ]
        response = ModelListResponse(
            models=models,
            total=2,
            cached=False,
        )
        assert len(response.models) == 2
        assert response.total == 2

    def test_empty_model_list(self):
        """Test empty model list."""
        response = ModelListResponse(models=[], total=0)
        assert len(response.models) == 0


# ProviderStatus Tests


@pytest.mark.fast
class TestProviderStatus:
    """Tests for ProviderStatus model."""

    def test_available_provider(self):
        """Test available provider status."""
        status = ProviderStatus(
            provider="google",
            available=True,
            models_count=3,
            default_text_model="gemini-3-pro-preview",
        )
        assert status.available is True
        assert status.models_count == 3

    def test_unavailable_provider(self):
        """Test unavailable provider status."""
        status = ProviderStatus(
            provider="openrouter",
            available=False,
            models_count=0,
        )
        assert status.available is False
        assert status.default_text_model is None


# ProvidersResponse Tests


@pytest.mark.fast
class TestProvidersResponse:
    """Tests for ProvidersResponse model."""

    def test_providers_response(self):
        """Test creating providers response."""
        providers = [
            ProviderStatus(provider="google", available=True, models_count=3),
            ProviderStatus(provider="openrouter", available=True, models_count=300),
        ]
        response = ProvidersResponse(providers=providers)
        assert len(response.providers) == 2


# get_configured_models Tests


@pytest.mark.fast
class TestGetConfiguredModels:
    """Tests for get_configured_models function."""

    def test_returns_list(self):
        """Test that function returns a list."""
        models = get_configured_models()
        assert isinstance(models, list)

    def test_models_have_required_fields(self):
        """Test that all models have required fields."""
        models = get_configured_models()
        for model in models:
            assert model.id is not None
            assert model.name is not None
            assert model.provider is not None
