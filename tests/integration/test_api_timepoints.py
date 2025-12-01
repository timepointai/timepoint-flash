"""Integration tests for timepoints API.

Tests:
    - Generate endpoint
    - Get timepoint by ID
    - Get timepoint by slug
    - List timepoints
"""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app
from app.models import Timepoint, TimepointStatus


# Test fixtures


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
async def async_client():
    """Create async test client."""
    from httpx import ASGITransport
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


# Generate Endpoint Tests


@pytest.mark.fast
class TestGenerateEndpointValidation:
    """Tests for POST /api/v1/timepoints/generate validation (no DB)."""

    def test_generate_request_validation(self, client):
        """Test request validation."""
        # Too short query
        response = client.post(
            "/api/v1/timepoints/generate",
            json={"query": "ab"},
        )
        assert response.status_code == 422

        # Empty query
        response = client.post(
            "/api/v1/timepoints/generate",
            json={"query": ""},
        )
        assert response.status_code == 422


@pytest.mark.integration
class TestGenerateEndpoint:
    """Tests for POST /api/v1/timepoints/generate (requires DB)."""

    def test_generate_endpoint_accepts_valid_query(self, client, test_db):
        """Test that valid query is accepted."""
        response = client.post(
            "/api/v1/timepoints/generate",
            json={"query": "signing of the declaration"},
        )
        # Should either succeed (200) or start processing (202)
        # In this case we're using background tasks so it returns immediately
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["status"] == "processing"


# Get Timepoint Tests


@pytest.mark.integration
class TestGetTimepointEndpoint:
    """Tests for GET /api/v1/timepoints/{id} (requires DB)."""

    def test_get_nonexistent_timepoint(self, client, test_db):
        """Test getting a non-existent timepoint."""
        response = client.get("/api/v1/timepoints/nonexistent-id")
        assert response.status_code == 404

    def test_get_timepoint_by_invalid_id(self, client, test_db):
        """Test getting timepoint with invalid ID format."""
        response = client.get("/api/v1/timepoints/not-a-uuid")
        assert response.status_code == 404


# Get by Slug Tests


@pytest.mark.integration
class TestGetBySlugEndpoint:
    """Tests for GET /api/v1/timepoints/slug/{slug} (requires DB)."""

    def test_get_nonexistent_slug(self, client, test_db):
        """Test getting a non-existent slug."""
        response = client.get("/api/v1/timepoints/slug/nonexistent-slug")
        assert response.status_code == 404


# List Timepoints Tests


@pytest.mark.fast
class TestListTimepointsValidation:
    """Tests for GET /api/v1/timepoints validation (no DB)."""

    def test_list_timepoints_invalid_page(self, client):
        """Test invalid page number."""
        response = client.get("/api/v1/timepoints?page=0")
        assert response.status_code == 422

    def test_list_timepoints_invalid_page_size(self, client):
        """Test invalid page size."""
        response = client.get("/api/v1/timepoints?page_size=0")
        assert response.status_code == 422

        response = client.get("/api/v1/timepoints?page_size=101")
        assert response.status_code == 422


@pytest.mark.integration
class TestListTimepointsEndpoint:
    """Tests for GET /api/v1/timepoints (requires DB)."""

    def test_list_timepoints_empty(self, client, test_db):
        """Test listing timepoints when empty."""
        response = client.get("/api/v1/timepoints")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data

    def test_list_timepoints_pagination_params(self, client, test_db):
        """Test pagination parameters."""
        response = client.get("/api/v1/timepoints?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10


# Response Model Tests


@pytest.mark.integration
class TestTimepointResponseModel:
    """Tests for response model structure (requires DB)."""

    def test_generate_response_structure(self, client, test_db):
        """Test generate response has correct structure."""
        response = client.post(
            "/api/v1/timepoints/generate",
            json={"query": "rome 50 BCE"},
        )
        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "id" in data
        assert "status" in data
        assert "message" in data

    def test_list_response_structure(self, client, test_db):
        """Test list response has correct structure."""
        response = client.get("/api/v1/timepoints")
        assert response.status_code == 200
        data = response.json()

        # Check pagination structure
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["page"], int)
        assert isinstance(data["page_size"], int)


# Integration with Database


@pytest.mark.integration
class TestDatabaseIntegration:
    """Integration tests that interact with database."""

    @pytest.mark.asyncio
    async def test_create_and_retrieve_timepoint(self, async_client, db_session):
        """Test creating and retrieving a timepoint."""
        # Create a timepoint directly in DB
        timepoint = Timepoint.create(
            query="test query",
            status=TimepointStatus.COMPLETED,
            year=1776,
        )
        db_session.add(timepoint)
        await db_session.commit()
        await db_session.refresh(timepoint)

        # Retrieve via API
        response = await async_client.get(f"/api/v1/timepoints/{timepoint.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "test query"
        assert data["year"] == 1776
