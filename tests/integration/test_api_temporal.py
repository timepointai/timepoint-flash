"""Integration tests for temporal navigation API.

Tests:
    - POST /api/v1/temporal/{id}/next - Generate next moment
    - POST /api/v1/temporal/{id}/prior - Generate prior moment
    - GET /api/v1/temporal/{id}/sequence - Get temporal sequence

Note: Tests that query database are marked @pytest.mark.integration
      and require database initialization via test_db fixture.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Timepoint, TimepointStatus


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


# Request Validation Tests (No Database Required)


@pytest.mark.fast
class TestNavigationRequestValidation:
    """Tests for navigation request validation (no DB required)."""

    def test_next_invalid_units_zero(self, client):
        """Test units cannot be zero."""
        response = client.post(
            "/api/v1/temporal/test-id/next",
            json={"units": 0, "unit": "day"},
        )
        assert response.status_code == 422

    def test_next_invalid_units_negative(self, client):
        """Test units cannot be negative."""
        response = client.post(
            "/api/v1/temporal/test-id/next",
            json={"units": -1, "unit": "day"},
        )
        assert response.status_code == 422

    def test_next_invalid_units_too_large(self, client):
        """Test units cannot exceed 365."""
        response = client.post(
            "/api/v1/temporal/test-id/next",
            json={"units": 400, "unit": "day"},
        )
        assert response.status_code == 422


@pytest.mark.fast
class TestSequenceEndpointValidation:
    """Tests for sequence endpoint validation (no DB required)."""

    def test_sequence_invalid_limit_zero(self, client):
        """Test sequence with invalid limit (zero)."""
        response = client.get("/api/v1/temporal/test-id/sequence?limit=0")
        assert response.status_code == 422

    def test_sequence_invalid_limit_too_large(self, client):
        """Test sequence with invalid limit (>50)."""
        response = client.get("/api/v1/temporal/test-id/sequence?limit=100")
        assert response.status_code == 422


# Database Required Tests


@pytest.mark.integration
class TestNavigationEndpointsExist:
    """Tests for navigation endpoints existence (requires DB)."""

    def test_next_endpoint_exists(self, client, test_db):
        """Test that next endpoint exists."""
        response = client.post(
            "/api/v1/temporal/test-id/next",
            json={"units": 1, "unit": "day"},
        )
        # Should return 404 (timepoint not found), not 405 (method not allowed)
        assert response.status_code == 404

    def test_prior_endpoint_exists(self, client, test_db):
        """Test that prior endpoint exists."""
        response = client.post(
            "/api/v1/temporal/test-id/prior",
            json={"units": 1, "unit": "day"},
        )
        assert response.status_code == 404

    def test_sequence_endpoint_exists(self, client, test_db):
        """Test that sequence endpoint exists."""
        response = client.get("/api/v1/temporal/test-id/sequence")
        assert response.status_code == 404

    def test_prior_default_values(self, client, test_db):
        """Test prior accepts empty body (uses defaults)."""
        response = client.post(
            "/api/v1/temporal/test-id/prior",
            json={},
        )
        # Should return 404 (timepoint not found), not 422 (validation error)
        assert response.status_code == 404


@pytest.mark.integration
class TestSequenceEndpointParams:
    """Tests for sequence endpoint parameters (requires DB)."""

    def test_sequence_with_direction_prior(self, client, test_db):
        """Test sequence with prior direction parameter."""
        response = client.get("/api/v1/temporal/test-id/sequence?direction=prior")
        assert response.status_code == 404

    def test_sequence_with_direction_next(self, client, test_db):
        """Test sequence with next direction parameter."""
        response = client.get("/api/v1/temporal/test-id/sequence?direction=next")
        assert response.status_code == 404

    def test_sequence_with_direction_both(self, client, test_db):
        """Test sequence with both direction parameter."""
        response = client.get("/api/v1/temporal/test-id/sequence?direction=both")
        assert response.status_code == 404

    def test_sequence_with_limit(self, client, test_db):
        """Test sequence with limit parameter."""
        response = client.get("/api/v1/temporal/test-id/sequence?limit=5")
        assert response.status_code == 404


# Time Unit Tests (Requires DB)


@pytest.mark.integration
class TestTimeUnits:
    """Tests for various time units in navigation (requires DB)."""

    @pytest.mark.parametrize("unit", ["day", "week", "month", "year"])
    def test_valid_time_units(self, client, test_db, unit):
        """Test that valid time units are accepted."""
        response = client.post(
            "/api/v1/temporal/test-id/next",
            json={"units": 1, "unit": unit},
        )
        # Should be 404 (not found) not 422 (validation error)
        assert response.status_code == 404

    @pytest.mark.parametrize("unit", ["second", "minute", "hour"])
    def test_small_time_units(self, client, test_db, unit):
        """Test that small time units are accepted."""
        response = client.post(
            "/api/v1/temporal/test-id/next",
            json={"units": 5, "unit": unit},
        )
        assert response.status_code == 404


# Response Structure Tests (Requires DB)


@pytest.mark.integration
class TestNavigationResponseStructure:
    """Tests for navigation response structure (requires DB)."""

    def test_next_response_structure(self, client, test_db):
        """Test that 404 response has proper structure."""
        response = client.post(
            "/api/v1/temporal/nonexistent-id/next",
            json={"units": 1, "unit": "day"},
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_sequence_response_structure(self, client, test_db):
        """Test that 404 response has proper structure."""
        response = client.get("/api/v1/temporal/nonexistent-id/sequence")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


# Error Cases (Requires DB)


@pytest.mark.integration
class TestNavigationErrors:
    """Tests for navigation error handling (requires DB)."""

    def test_next_nonexistent_timepoint(self, client, test_db):
        """Test next with non-existent timepoint."""
        response = client.post(
            "/api/v1/temporal/00000000-0000-0000-0000-000000000000/next",
            json={"units": 1, "unit": "day"},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_prior_nonexistent_timepoint(self, client, test_db):
        """Test prior with non-existent timepoint."""
        response = client.post(
            "/api/v1/temporal/00000000-0000-0000-0000-000000000000/prior",
            json={"units": 1, "unit": "day"},
        )
        assert response.status_code == 404

    def test_sequence_nonexistent_timepoint(self, client, test_db):
        """Test sequence with non-existent timepoint."""
        response = client.get(
            "/api/v1/temporal/00000000-0000-0000-0000-000000000000/sequence"
        )
        assert response.status_code == 404
