"""Unit tests for FastAPI application.

Tests for app/main.py - API endpoints and application setup.

Run with:
    pytest tests/unit/test_main.py -v
    pytest tests/unit/test_main.py -v -m fast
"""

import pytest


@pytest.mark.fast
class TestRootEndpoint:
    """Tests for root endpoint."""

    @pytest.mark.asyncio
    async def test_root_returns_info(self, test_client):
        """Test root endpoint returns application info."""
        response = await test_client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "TIMEPOINT Flash"
        assert "version" in data
        assert data["docs"] == "/docs"
        assert data["health"] == "/health"


@pytest.mark.fast
class TestHealthEndpoint:
    """Tests for health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_status(self, test_client):
        """Test health endpoint returns status."""
        response = await test_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "database" in data
        assert "providers" in data

    @pytest.mark.asyncio
    async def test_health_includes_providers(self, test_client):
        """Test health endpoint includes provider status."""
        response = await test_client.get("/health")
        data = response.json()

        # Should have provider info (configured via test env)
        assert "google" in data["providers"]
        assert "openrouter" in data["providers"]


@pytest.mark.fast
class TestAPIStatusEndpoint:
    """Tests for API status endpoint."""

    @pytest.mark.asyncio
    async def test_api_status_returns_info(self, test_client):
        """Test API status endpoint returns configuration info."""
        response = await test_client.get("/api/v1/status")
        assert response.status_code == 200

        data = response.json()
        assert data["api_version"] == "v1"
        assert "app_version" in data
        assert "environment" in data
        assert "primary_provider" in data
        assert "models" in data

    @pytest.mark.asyncio
    async def test_api_status_includes_models(self, test_client):
        """Test API status includes model configuration."""
        response = await test_client.get("/api/v1/status")
        data = response.json()

        models = data["models"]
        assert "judge" in models
        assert "creative" in models
        assert "image" in models


@pytest.mark.fast
class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, test_client):
        """Test non-existent endpoint returns 404."""
        response = await test_client.get("/api/v1/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_method_not_allowed(self, test_client):
        """Test wrong method returns 405."""
        response = await test_client.post("/health")
        assert response.status_code == 405
