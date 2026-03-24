"""
E2E tests for API behavior and features.

Tests:
- Concurrent requests
- Feed/list pagination
- Error handling (invalid queries)
- Health endpoint
- Invalid slug handling

Run with: pytest tests/test_e2e_api.py -v
"""

from __future__ import annotations

import asyncio

import pytest

# Endpoint paths
GENERATE_ENDPOINT = "/api/v1/timepoints/generate"
LIST_ENDPOINT = "/api/v1/timepoints"
GET_BY_SLUG_ENDPOINT = "/api/v1/timepoints/slug/{slug}"
HEALTH_ENDPOINT = "/health"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_pagination(test_client, e2e_test_db):
    """Test that list endpoint supports pagination."""
    # Test basic list retrieval
    response = await test_client.get(f"{LIST_ENDPOINT}?page=1&page_size=5")
    assert response.status_code == 200

    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert data["page"] == 1
    assert data["page_size"] == 5

    # Test second page
    response_page2 = await test_client.get(f"{LIST_ENDPOINT}?page=2&page_size=5")
    assert response_page2.status_code == 200


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_invalid_query_handling(test_client, e2e_test_db):
    """Test handling of invalid/malformed queries."""
    # Empty query - should be rejected (min_length=3)
    response = await test_client.post(
        GENERATE_ENDPOINT,
        json={"query": ""},
    )
    assert response.status_code == 422, (
        f"Empty query should be rejected, got {response.status_code}"
    )

    # Too short query (min_length=3)
    response = await test_client.post(
        GENERATE_ENDPOINT,
        json={"query": "a"},
    )
    assert response.status_code == 422, (
        f"Too-short query should be rejected, got {response.status_code}"
    )

    # Too long query (max_length=500)
    response = await test_client.post(
        GENERATE_ENDPOINT,
        json={"query": "x" * 501},
    )
    assert response.status_code == 422, (
        f"Too-long query should be rejected, got {response.status_code}"
    )

    # Missing query field entirely
    response = await test_client.post(
        GENERATE_ENDPOINT,
        json={},
    )
    assert response.status_code == 422, (
        f"Missing query should be rejected, got {response.status_code}"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_concurrent_requests(test_client, e2e_test_db):
    """Test handling of multiple concurrent requests."""

    async def create_timepoint(index: int):
        response = await test_client.post(
            GENERATE_ENDPOINT,
            json={"query": f"Historical event number {index}, year {1500 + index}"},
        )
        return response.status_code

    # Create 3 concurrent requests
    tasks = [create_timepoint(i) for i in range(3)]
    results = await asyncio.gather(*tasks)

    # All should be accepted
    successful = sum(1 for code in results if code == 200)
    assert successful >= 2, f"Only {successful}/3 concurrent requests succeeded"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_invalid_slug_returns_404(test_client, e2e_test_db):
    """Test that invalid slugs return 404."""
    response = await test_client.get(GET_BY_SLUG_ENDPOINT.format(slug="nonexistent-slug-12345"))

    assert response.status_code == 404


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_health_endpoint_responds(test_client, e2e_test_db):
    """Test that health endpoint is responsive."""
    response = await test_client.get(HEALTH_ENDPOINT)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "version" in data
    assert "database" in data
    assert "providers" in data


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_generate_returns_processing_status(test_client, e2e_test_db):
    """Test that generate endpoint returns processing status."""
    response = await test_client.post(
        GENERATE_ENDPOINT,
        json={"query": "Battle of Thermopylae, 480 BCE"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processing"
    assert "id" in data
    assert "message" in data


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_invalid_timepoint_id_returns_404(test_client, e2e_test_db):
    """Test that invalid timepoint ID returns 404."""
    response = await test_client.get("/api/v1/timepoints/nonexistent-id-99999")

    assert response.status_code == 404
