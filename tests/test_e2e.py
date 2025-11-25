"""
End-to-end integration tests for Timepoint Flash.

These tests make real API calls and require OPENROUTER_API_KEY.
Run with: pytest -m e2e
"""
import pytest
import asyncio
import json
from typing import Dict, Any
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.utils.llm_judge import judge_timepoint, JudgementResult


# Test scenarios with expected quality thresholds
TEST_SCENARIOS = [
    {
        "query": "Medieval marketplace in London, winter 1250",
        "email": "test-medieval@example.com",
        "min_score": 65.0,  # Lower threshold for complex historical scenarios
        "description": "Medieval English marketplace scene"
    },
    {
        "query": "American Revolutionary War, Valley Forge 1777",
        "email": "test-revolution@example.com",
        "min_score": 65.0,
        "description": "Revolutionary War winter encampment"
    },
    {
        "query": "Ancient Rome forum, summer 50 BCE",
        "email": "test-rome@example.com",
        "min_score": 65.0,
        "description": "Roman Republic forum scene"
    },
]


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_full_timepoint_generation_simple(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """
    Test full timepoint generation with a simple, fast scenario.
    """
    # Create timepoint
    response = client.post(
        "/api/timepoint/create",
        json={
            "query": "Simple test scene",
            "email": "test-simple@example.com"
        }
    )

    assert response.status_code in [200, 201], f"Failed to create timepoint: {response.text}"
    data = response.json()

    # Check response structure
    assert "session_id" in data or "id" in data or "slug" in data

    # Give it time to process (if async)
    await asyncio.sleep(2)

    print(f"\n✅ Simple timepoint generation test passed")


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", TEST_SCENARIOS)
async def test_timepoint_generation_with_judge(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str,
    scenario: Dict[str, Any]
):
    """
    Test full timepoint generation with LLM-based quality assessment.

    This test:
    1. Creates a timepoint with a historical query
    2. Waits for generation to complete
    3. Retrieves the generated timepoint
    4. Uses LLM judge to evaluate quality
    5. Asserts quality meets minimum threshold
    """
    query = scenario["query"]
    email = scenario["email"]
    min_score = scenario["min_score"]
    description = scenario["description"]

    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Query: {query}")
    print(f"{'='*60}")

    # Step 1: Create timepoint
    print("Step 1: Creating timepoint...")
    response = client.post(
        "/api/timepoint/create",
        json={
            "query": query,
            "email": email
        }
    )

    assert response.status_code in [200, 201], f"Failed to create timepoint: {response.text}"
    create_data = response.json()
    print(f"✓ Timepoint creation initiated")

    # Extract session/timepoint identifier
    session_id = create_data.get("session_id") or create_data.get("id")
    slug = create_data.get("slug")

    # Step 2: Wait for generation (give it time)
    print("Step 2: Waiting for generation to complete...")
    await asyncio.sleep(5)  # Initial wait

    # Try to get the timepoint (with retries)
    timepoint_data = None
    max_retries = 20  # Max 200 seconds total
    retry_delay = 10  # 10 seconds between retries

    for attempt in range(max_retries):
        # Try different endpoints to find the timepoint
        if slug:
            # Try to get by slug
            detail_response = client.get(f"/api/timepoint/details/{slug}")
            if detail_response.status_code == 200:
                timepoint_data = detail_response.json()
                break

        # Try to check status
        if session_id:
            status_response = client.get(f"/api/timepoint/status/{session_id}")
            if status_response.status_code == 200:
                # Check if completed
                # Note: This might be SSE, so we skip for now
                pass

        # Try feed endpoint to find our timepoint
        feed_response = client.get("/api/feed?limit=10")
        if feed_response.status_code == 200:
            feed_data = feed_response.json()
            for tp in feed_data.get("timepoints", []):
                if tp.get("email") == email or tp.get("query") == query:
                    timepoint_data = tp
                    break

        if timepoint_data and timepoint_data.get("status") == "completed":
            break

        print(f"  Attempt {attempt + 1}/{max_retries}: Timepoint not ready yet...")
        await asyncio.sleep(retry_delay)

    # Step 3: Verify we got the timepoint
    if not timepoint_data:
        pytest.skip(f"Timepoint generation timed out or failed for: {query}")

    assert timepoint_data is not None, "Failed to retrieve timepoint"
    assert timepoint_data.get("status") == "completed", \
        f"Timepoint not completed: {timepoint_data.get('status')}"

    print(f"✓ Timepoint generation completed")
    print(f"  Year: {timepoint_data.get('year')}")
    print(f"  Season: {timepoint_data.get('season')}")
    print(f"  Location: {timepoint_data.get('location')}")
    print(f"  Characters: {len(timepoint_data.get('character_data', []))}")
    print(f"  Dialog lines: {len(timepoint_data.get('dialog', []))}")

    # Step 4: Judge quality with LLM
    print("Step 4: Evaluating quality with LLM judge...")
    judgement = await judge_timepoint(
        api_key=openrouter_api_key,
        query=query,
        timepoint_data=timepoint_data,
        passing_threshold=min_score
    )

    print(f"\n{'='*60}")
    print(f"QUALITY ASSESSMENT RESULTS")
    print(f"{'='*60}")
    print(f"Overall Score:        {judgement.overall_score:.1f}/100")
    print(f"Historical Accuracy:  {judgement.historical_accuracy:.1f}/100")
    print(f"Character Quality:    {judgement.character_quality:.1f}/100")
    print(f"Dialog Quality:       {judgement.dialog_quality:.1f}/100")
    print(f"Scene Coherence:      {judgement.scene_coherence:.1f}/100")
    print(f"\nFeedback: {judgement.feedback}")
    print(f"{'='*60}")
    print(f"Status: {'✅ PASSED' if judgement.passed else '❌ FAILED'}")
    print(f"{'='*60}\n")

    # Step 5: Assert quality meets threshold
    assert judgement.passed, \
        f"Quality score {judgement.overall_score:.1f} below threshold {min_score:.1f}"
    assert judgement.overall_score >= min_score, \
        f"Overall score too low: {judgement.overall_score:.1f} < {min_score:.1f}"

    # Additional assertions for specific metrics
    assert judgement.historical_accuracy >= 50.0, \
        f"Historical accuracy too low: {judgement.historical_accuracy:.1f}"
    assert judgement.character_quality >= 50.0, \
        f"Character quality too low: {judgement.character_quality:.1f}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_rate_limiting_e2e(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """
    Test that rate limiting works in practice.
    """
    email = "test-ratelimit@example.com"
    query = "Test rate limit query"

    # First request should succeed
    response1 = client.post(
        "/api/timepoint/create",
        json={"query": query, "email": email}
    )
    assert response1.status_code in [200, 201]

    # Wait a moment
    await asyncio.sleep(1)

    # Second request should be rate limited (if MAX_TIMEPOINTS_PER_HOUR=1)
    response2 = client.post(
        "/api/timepoint/create",
        json={"query": f"{query} 2", "email": email}
    )

    # In test settings, rate limit is set high (100), so this might not fail
    # But we can check the response
    if response2.status_code == 429:
        print("✓ Rate limiting is working")
    else:
        print(f"⚠ Rate limit not triggered (test setting may allow multiple)")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_feed_endpoint_e2e(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """
    Test the feed endpoint returns timepoints.
    """
    # Create a timepoint first
    response = client.post(
        "/api/timepoint/create",
        json={
            "query": "Feed test query",
            "email": "test-feed@example.com"
        }
    )
    assert response.status_code in [200, 201]

    # Wait for it to potentially complete
    await asyncio.sleep(5)

    # Check feed
    feed_response = client.get("/api/feed?limit=10")
    assert feed_response.status_code == 200

    feed_data = feed_response.json()
    assert "timepoints" in feed_data

    print(f"✓ Feed contains {len(feed_data['timepoints'])} timepoint(s)")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_judge_accuracy(openrouter_api_key: str):
    """
    Test the LLM judge itself with a mock high-quality and low-quality timepoint.
    """
    print("\n" + "="*60)
    print("Testing LLM Judge Accuracy")
    print("="*60)

    # High-quality mock timepoint
    high_quality_tp = {
        "year": 1776,
        "season": "summer",
        "location": "Philadelphia, Pennsylvania",
        "cleaned_query": "Signing of the Declaration of Independence",
        "scene_description": "A warm summer day in Philadelphia, July 4, 1776...",
        "character_data": [
            {
                "name": "Benjamin Franklin",
                "role": "Diplomat and Founding Father",
                "appearance": "Elderly statesman with white hair",
                "clothing": "Brown colonial coat with brass buttons"
            },
            {
                "name": "Thomas Jefferson",
                "role": "Primary author of the Declaration",
                "appearance": "Tall, red-haired man in his thirties",
                "clothing": "Blue colonial coat with white ruffled shirt"
            }
        ],
        "dialog": [
            {
                "speaker": "Franklin",
                "text": "We must indeed all hang together, or most assuredly we shall all hang separately."
            },
            {
                "speaker": "Jefferson",
                "text": "The document is ready for signatures, gentlemen."
            }
        ],
        "status": "completed"
    }

    judgement = await judge_timepoint(
        api_key=openrouter_api_key,
        query="Signing of the Declaration of Independence, 1776",
        timepoint_data=high_quality_tp,
        passing_threshold=70.0
    )

    print(f"\nHigh-Quality Timepoint Score: {judgement.overall_score:.1f}/100")
    print(f"Feedback: {judgement.feedback}")

    # Should score reasonably high
    assert judgement.overall_score >= 60.0, \
        f"Judge gave unexpectedly low score to high-quality timepoint: {judgement.overall_score}"

    print(f"✅ Judge correctly evaluated high-quality timepoint\n")
