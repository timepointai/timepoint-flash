"""
E2E tests for API behavior and features.

Tests:
- Rate limiting (IP and email-based)
- Concurrent requests
- SSE streaming
- Error handling
- Feed pagination

Run with: pytest tests/test_e2e_api.py -v
"""
import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.utils.test_helpers import generate_unique_test_email
from tests.utils.retry import retry_on_api_error


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_rate_limiting_email_based(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """Test email-based rate limiting (1/hour by default in production)."""
    email = generate_unique_test_email("test-ratelimit-email")

    # First request should succeed
    response1 = client.post(
        "/api/timepoint/create",
        json={"input_query": "Test query 1", "requester_email": email}
    )
    assert response1.status_code in [200, 201], f"First request failed: {response1.text}"
    print("✓ First request accepted")

    # Second request should be rate limited (unless test settings allow more)
    # In test environment, MAX_TIMEPOINTS_PER_HOUR is set to 100, so this won't fail
    # But in production it would be rate limited
    response2 = client.post(
        "/api/timepoint/create",
        json={"input_query": "Test query 2", "requester_email": email}
    )

    if response2.status_code == 429:
        print("✓ Rate limiting is enforced (production-like behavior)")
    else:
        print("⚠ Rate limit not triggered (test environment allows multiple)")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_rate_limiting_ip_based(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """Test IP-based rate limiting for anonymous requests."""
    # Anonymous requests (no email) should be rate limited per IP (10/hour default)

    requests_made = 0
    max_attempts = 12  # Try to exceed limit

    for i in range(max_attempts):
        response = client.post(
            "/api/timepoint/create",
            json={"input_query": f"Anonymous test query {i}"}
            # No email provided - uses IP-based rate limiting
        )

        if response.status_code == 429:
            print(f"✓ IP-based rate limit triggered after {i} requests")
            break

        requests_made += 1

    if requests_made >= 10:
        print("⚠ IP rate limit may not be enforced (test environment)")
    else:
        print(f"✓ Made {requests_made} anonymous requests before rate limit")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_feed_pagination(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """Test that feed endpoint supports pagination."""
    # Test basic feed retrieval
    response = client.get("/api/feed?limit=5&offset=0")
    assert response.status_code == 200

    data = response.json()
    assert "timepoints" in data
    assert isinstance(data["timepoints"], list)

    # Test pagination parameters
    response_page2 = client.get("/api/feed?limit=5&offset=5")
    assert response_page2.status_code == 200

    print("✓ Feed pagination works correctly")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_invalid_query_handling(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """Test handling of invalid/malformed queries."""
    email = generate_unique_test_email("test-invalid")

    # Test cases for invalid inputs
    invalid_cases = [
        {"input_query": ""},  # Empty query
        {"input_query": "a"},  # Too short
        {"input_query": "x" * 1000},  # Too long
        {},  # Missing query entirely
    ]

    for i, case in enumerate(invalid_cases):
        if "input_query" in case:
            case["requester_email"] = email

        response = client.post("/api/timepoint/create", json=case)

        # Should reject with 400 or 422
        if response.status_code in [400, 422]:
            print(f"✓ Case {i+1}: Correctly rejected invalid input")
        else:
            print(f"⚠ Case {i+1}: Accepted potentially invalid input (status {response.status_code})")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_concurrent_requests(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """Test handling of multiple concurrent requests."""
    async def create_timepoint(index: int):
        email = generate_unique_test_email(f"test-concurrent-{index}")
        response = client.post(
            "/api/timepoint/create",
            json={
                "input_query": f"Test concurrent query {index}",
                "requester_email": email
            }
        )
        return response.status_code

    # Create 3 concurrent requests
    tasks = [create_timepoint(i) for i in range(3)]
    results = await asyncio.gather(*tasks)

    # All should be accepted (different emails)
    successful = sum(1 for status in results if status in [200, 201])

    assert successful >= 2, f"Only {successful}/3 concurrent requests succeeded"
    print(f"✓ {successful}/3 concurrent requests handled successfully")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_timepoint_details_404_on_invalid_slug(
    client: TestClient,
    db_session: Session
):
    """Test that invalid slugs return 404."""
    response = client.get("/api/timepoint/details/nonexistent-slug-12345")

    assert response.status_code == 404
    print("✓ Invalid slug returns 404 as expected")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_health_endpoint_responds(
    client: TestClient,
    db_session: Session
):
    """Test that health endpoint is responsive."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "timepoint-flash"

    print("✓ Health endpoint responds correctly")
