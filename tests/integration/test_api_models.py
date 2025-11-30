"""Integration tests for model discovery API.

Tests:
    - GET /api/v1/models - List available models
    - GET /api/v1/models/providers - Get provider status
    - GET /api/v1/models/{model_id} - Get model details
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


# List Models Tests


@pytest.mark.fast
class TestListModelsEndpoint:
    """Tests for GET /api/v1/models."""

    def test_list_models_returns_200(self, client):
        """Test that list models returns 200."""
        response = client.get("/api/v1/models")
        assert response.status_code == 200

    def test_list_models_response_structure(self, client):
        """Test list models response structure."""
        response = client.get("/api/v1/models")
        assert response.status_code == 200
        data = response.json()

        assert "models" in data
        assert "total" in data
        assert "cached" in data
        assert isinstance(data["models"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["cached"], bool)

    def test_list_models_model_structure(self, client):
        """Test individual model structure in list."""
        response = client.get("/api/v1/models")
        assert response.status_code == 200
        data = response.json()

        # Should have models since test has API keys set
        if data["models"]:
            model = data["models"][0]
            assert "id" in model
            assert "name" in model
            assert "provider" in model
            assert "capabilities" in model
            assert "is_available" in model

    def test_list_models_with_provider_filter(self, client):
        """Test filtering models by provider."""
        response = client.get("/api/v1/models?provider=google")
        assert response.status_code == 200
        data = response.json()

        # All returned models should be from Google
        for model in data["models"]:
            assert model["provider"] == "google"

    def test_list_models_with_capability_filter(self, client):
        """Test filtering models by capability."""
        response = client.get("/api/v1/models?capability=text")
        assert response.status_code == 200
        data = response.json()

        # All returned models should have text capability
        for model in data["models"]:
            assert "text" in model["capabilities"]

    def test_list_models_with_image_capability(self, client):
        """Test filtering models by image_generation capability."""
        response = client.get("/api/v1/models?capability=image_generation")
        assert response.status_code == 200
        data = response.json()

        # All returned models should have image_generation capability
        for model in data["models"]:
            assert "image_generation" in model["capabilities"]

    def test_list_models_combined_filters(self, client):
        """Test combining provider and capability filters."""
        response = client.get("/api/v1/models?provider=google&capability=text")
        assert response.status_code == 200
        data = response.json()

        for model in data["models"]:
            assert model["provider"] == "google"
            assert "text" in model["capabilities"]

    def test_list_models_fetch_remote_param(self, client):
        """Test fetch_remote parameter exists."""
        response = client.get("/api/v1/models?fetch_remote=false")
        assert response.status_code == 200


# Provider Status Tests


@pytest.mark.fast
class TestProvidersEndpoint:
    """Tests for GET /api/v1/models/providers."""

    def test_providers_returns_200(self, client):
        """Test that providers endpoint returns 200."""
        response = client.get("/api/v1/models/providers")
        assert response.status_code == 200

    def test_providers_response_structure(self, client):
        """Test providers response structure."""
        response = client.get("/api/v1/models/providers")
        assert response.status_code == 200
        data = response.json()

        assert "providers" in data
        assert isinstance(data["providers"], list)

    def test_providers_have_required_fields(self, client):
        """Test each provider has required fields."""
        response = client.get("/api/v1/models/providers")
        assert response.status_code == 200
        data = response.json()

        for provider in data["providers"]:
            assert "provider" in provider
            assert "available" in provider
            assert "models_count" in provider
            assert isinstance(provider["available"], bool)
            assert isinstance(provider["models_count"], int)

    def test_providers_includes_google(self, client):
        """Test that Google provider is included."""
        response = client.get("/api/v1/models/providers")
        assert response.status_code == 200
        data = response.json()

        provider_names = [p["provider"] for p in data["providers"]]
        assert "google" in provider_names

    def test_providers_includes_openrouter(self, client):
        """Test that OpenRouter provider is included."""
        response = client.get("/api/v1/models/providers")
        assert response.status_code == 200
        data = response.json()

        provider_names = [p["provider"] for p in data["providers"]]
        assert "openrouter" in provider_names


# Get Model Details Tests


@pytest.mark.fast
class TestGetModelEndpoint:
    """Tests for GET /api/v1/models/{model_id}."""

    def test_get_nonexistent_model(self, client):
        """Test getting a non-existent model returns 404."""
        response = client.get("/api/v1/models/nonexistent-model-id")
        assert response.status_code == 404

    def test_get_model_404_structure(self, client):
        """Test 404 response structure."""
        response = client.get("/api/v1/models/nonexistent-model-id")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_get_configured_model(self, client):
        """Test getting a configured model."""
        # First list models to get a valid ID
        list_response = client.get("/api/v1/models")
        assert list_response.status_code == 200
        models = list_response.json()["models"]

        if models:
            model_id = models[0]["id"]
            response = client.get(f"/api/v1/models/{model_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == model_id

    def test_get_model_with_path_chars(self, client):
        """Test model ID with path-like characters (OpenRouter format)."""
        # OpenRouter model IDs contain slashes like "anthropic/claude-3.5-sonnet"
        response = client.get("/api/v1/models/anthropic/claude-3.5-sonnet")
        # Should return 404 (not found) or 200 (if configured), not 405
        assert response.status_code in [200, 404]


# Edge Cases


@pytest.mark.fast
class TestModelsEdgeCases:
    """Edge case tests for models API."""

    def test_empty_provider_filter(self, client):
        """Test empty provider filter is ignored."""
        response = client.get("/api/v1/models?provider=")
        # Should work but may return all models
        assert response.status_code in [200, 422]

    def test_invalid_provider_filter(self, client):
        """Test invalid provider returns empty list."""
        response = client.get("/api/v1/models?provider=invalid-provider")
        assert response.status_code == 200
        data = response.json()
        assert data["models"] == []
        assert data["total"] == 0

    def test_invalid_capability_filter(self, client):
        """Test invalid capability returns empty list."""
        response = client.get("/api/v1/models?capability=invalid-capability")
        assert response.status_code == 200
        data = response.json()
        assert data["models"] == []
