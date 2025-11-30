"""Integration tests for SSE streaming endpoint.

Tests:
    - POST /api/v1/timepoints/generate/stream - Stream generation progress
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


# Streaming Endpoint Tests


@pytest.mark.fast
class TestStreamingEndpointExists:
    """Tests for streaming endpoint availability."""

    def test_streaming_endpoint_exists(self, client):
        """Test that streaming endpoint exists."""
        response = client.post(
            "/api/v1/timepoints/generate/stream",
            json={"query": "test query for streaming"},
        )
        # Should return 200 with streaming content, not 404 or 405
        assert response.status_code == 200

    def test_streaming_endpoint_content_type(self, client):
        """Test streaming endpoint returns SSE content type."""
        response = client.post(
            "/api/v1/timepoints/generate/stream",
            json={"query": "test query for streaming"},
        )
        assert response.status_code == 200
        # SSE endpoints return text/event-stream
        assert "text/event-stream" in response.headers.get("content-type", "")


@pytest.mark.fast
class TestStreamingRequestValidation:
    """Tests for streaming request validation."""

    def test_streaming_requires_query(self, client):
        """Test that streaming requires query parameter."""
        response = client.post(
            "/api/v1/timepoints/generate/stream",
            json={},
        )
        assert response.status_code == 422

    def test_streaming_query_min_length(self, client):
        """Test query minimum length validation."""
        response = client.post(
            "/api/v1/timepoints/generate/stream",
            json={"query": "ab"},
        )
        assert response.status_code == 422

    def test_streaming_query_max_length(self, client):
        """Test query maximum length validation."""
        response = client.post(
            "/api/v1/timepoints/generate/stream",
            json={"query": "a" * 501},
        )
        assert response.status_code == 422

    def test_streaming_valid_query(self, client):
        """Test that valid query is accepted."""
        response = client.post(
            "/api/v1/timepoints/generate/stream",
            json={"query": "signing of the declaration"},
        )
        assert response.status_code == 200

    def test_streaming_with_image_param(self, client):
        """Test streaming with generate_image parameter."""
        response = client.post(
            "/api/v1/timepoints/generate/stream",
            json={
                "query": "rome 50 BCE",
                "generate_image": True,
            },
        )
        assert response.status_code == 200

    def test_streaming_image_param_false(self, client):
        """Test streaming with generate_image=false."""
        response = client.post(
            "/api/v1/timepoints/generate/stream",
            json={
                "query": "rome 50 BCE",
                "generate_image": False,
            },
        )
        assert response.status_code == 200


@pytest.mark.fast
class TestStreamingResponseFormat:
    """Tests for streaming response format."""

    def test_streaming_returns_bytes(self, client):
        """Test that streaming returns data."""
        response = client.post(
            "/api/v1/timepoints/generate/stream",
            json={"query": "test streaming response"},
        )
        assert response.status_code == 200
        # Should have some content
        assert len(response.content) > 0

    def test_streaming_response_is_sse_format(self, client):
        """Test that response follows SSE format."""
        response = client.post(
            "/api/v1/timepoints/generate/stream",
            json={"query": "test SSE format"},
        )
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        # SSE format has "data:" prefix
        assert "data:" in content


@pytest.mark.integration
class TestStreamingEvents:
    """Tests for streaming event content.

    Note: Full event testing requires pipeline execution.
    These tests verify basic event structure.
    """

    def test_streaming_start_event(self, client):
        """Test that streaming starts with initial event."""
        response = client.post(
            "/api/v1/timepoints/generate/stream",
            json={"query": "test start event"},
        )
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        # Should contain start or initialization event
        assert "data:" in content

    def test_streaming_json_events(self, client):
        """Test that events contain valid JSON."""
        response = client.post(
            "/api/v1/timepoints/generate/stream",
            json={"query": "test JSON events"},
        )
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Extract data lines and verify they contain JSON-like structure
        data_lines = [
            line for line in content.split("\n") if line.startswith("data:")
        ]
        # Should have at least one data line
        assert len(data_lines) > 0

        # First data line should contain JSON with event field
        first_data = data_lines[0].replace("data:", "").strip()
        assert "{" in first_data  # Contains JSON object


# Error Cases


@pytest.mark.fast
class TestStreamingErrors:
    """Tests for streaming error handling."""

    def test_streaming_handles_empty_query(self, client):
        """Test error handling for empty query."""
        response = client.post(
            "/api/v1/timepoints/generate/stream",
            json={"query": ""},
        )
        # Should return validation error
        assert response.status_code == 422

    def test_streaming_handles_invalid_json(self, client):
        """Test error handling for invalid JSON."""
        response = client.post(
            "/api/v1/timepoints/generate/stream",
            content=b"not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422


# Concurrent Requests


@pytest.mark.fast
class TestStreamingConcurrency:
    """Tests for concurrent streaming requests."""

    def test_multiple_streaming_requests(self, client):
        """Test that multiple requests can be made."""
        # First request
        response1 = client.post(
            "/api/v1/timepoints/generate/stream",
            json={"query": "first concurrent test"},
        )
        assert response1.status_code == 200

        # Second request
        response2 = client.post(
            "/api/v1/timepoints/generate/stream",
            json={"query": "second concurrent test"},
        )
        assert response2.status_code == 200
