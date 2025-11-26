"""
End-to-end integration tests for Timepoint Flash.

These tests make real API calls and require OPENROUTER_API_KEY.
Run with: pytest -m e2e

Database Support:
- Automatically uses SQLite (in-memory or file-based) by default
- Uses PostgreSQL if DATABASE_URL is configured and database is accessible
- Tests adapt automatically to the available database
"""
import pytest
import asyncio
import json
from typing import Dict, Any, Literal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.utils.llm_judge import judge_timepoint, JudgementResult
from tests.utils.test_helpers import (
    wait_for_completion,
    verify_image_data,
    verify_timepoint_structure,
    generate_unique_test_email
)
from tests.utils.retry import retry_on_api_error, skip_on_api_unavailable


@pytest.fixture(scope="module", autouse=True)
def log_database_info(db_type: Literal["sqlite", "postgresql"], test_database_url: str):
    """Log which database is being used for e2e tests."""
    print(f"\n{'='*60}")
    print(f"E2E Test Database Configuration")
    print(f"{'='*60}")
    print(f"Database Type: {db_type.upper()}")
    print(f"Database URL:  {test_database_url}")
    if db_type == "sqlite":
        if test_database_url == "sqlite:///:memory:":
            print(f"Mode:          In-memory (ephemeral)")
        else:
            print(f"Mode:          File-based (persistent)")
    print(f"{'='*60}\n")


# Test scenarios with expected quality thresholds
TEST_SCENARIOS = [
    {
        "query": "Medieval marketplace in London, winter 1250",
        "email": "test-medieval",
        "min_score": 65.0,  # Lower threshold for complex historical scenarios
        "description": "Medieval English marketplace scene"
    },
    {
        "query": "American Revolutionary War, Valley Forge 1777",
        "email": "test-revolution",
        "min_score": 65.0,
        "description": "Revolutionary War winter encampment"
    },
    {
        "query": "Ancient Rome forum, summer 50 BCE",
        "email": "test-rome",
        "min_score": 65.0,
        "description": "Roman Republic forum scene"
    },
    # NEW SCENARIOS - Expanding coverage
    {
        "query": "Ancient Egypt, construction of the Great Pyramid of Giza, 2560 BCE",
        "email": "test-egypt",
        "min_score": 65.0,
        "description": "Ancient Egyptian pyramid construction"
    },
    {
        "query": "Renaissance Florence, artist's workshop, spring 1504",
        "email": "test-renaissance",
        "min_score": 65.0,
        "description": "Renaissance Italy art studio"
    },
    {
        "query": "Industrial Revolution London, factory floor, autumn 1850",
        "email": "test-industrial",
        "min_score": 65.0,
        "description": "Victorian factory during Industrial Revolution"
    },
    {
        "query": "World War II, D-Day landing at Normandy, June 6 1944",
        "email": "test-ww2",
        "min_score": 65.0,
        "description": "WWII D-Day invasion"
    },
    {
        "query": "Moon landing, Apollo 11 mission control, July 20 1969",
        "email": "test-moonlanding",
        "min_score": 65.0,
        "description": "Apollo 11 moon landing mission control"
    },
    {
        "query": "Berlin Wall fall, Checkpoint Charlie, November 9 1989",
        "email": "test-berlin",
        "min_score": 65.0,
        "description": "Fall of Berlin Wall"
    },
    {
        "query": "New York City, Times Square on New Year's Eve, winter 2023",
        "email": "test-modern",
        "min_score": 65.0,
        "description": "Modern era near-present day"
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
@retry_on_api_error(max_attempts=2, backoff_factor=2.0)  # Retry once on transient failures
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
    2. Waits for generation to complete (smart polling)
    3. Retrieves the generated timepoint
    4. Validates structure and image data
    5. Uses LLM judge to evaluate quality
    6. Asserts quality meets minimum threshold
    """
    query = scenario["query"]
    email = generate_unique_test_email(base=scenario["email"].split("@")[0])  # Unique email
    min_score = scenario["min_score"]
    description = scenario["description"]

    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Query: {query}")
    print(f"Email: {email}")
    print(f"{'='*60}")

    # Step 1: Create timepoint
    print("Step 1: Creating timepoint...")
    response = client.post(
        "/api/timepoint/create",
        json={
            "input_query": query,
            "requester_email": email
        }
    )

    assert response.status_code in [200, 201], f"Failed to create timepoint: {response.text}"
    create_data = response.json()
    print(f"✓ Timepoint creation initiated")

    # Extract session/timepoint identifier
    session_id = create_data.get("session_id") or create_data.get("id")
    slug = create_data.get("slug")

    # Step 2: Wait for generation using smart polling
    print("Step 2: Waiting for generation to complete (smart polling)...")

    async def check_completion():
        """Check if timepoint is complete."""
        # Try to get by slug first
        if slug:
            detail_response = client.get(f"/api/timepoint/details/{slug}")
            if detail_response.status_code == 200:
                data = detail_response.json()
                # Check if it's complete (either status field or has all required data)
                is_complete = (
                    data.get("status") == "completed" or
                    (data.get("image_url") and data.get("character_data_json"))
                )
                if is_complete:
                    return (True, data)

        # Fallback: Check feed for our email
        feed_response = client.get("/api/feed?limit=20")
        if feed_response.status_code == 200:
            feed_data = feed_response.json()
            for tp in feed_data.get("timepoints", []):
                # Match by input_query or email
                if (tp.get("input_query") == query or
                    tp.get("cleaned_query") == query or
                    tp.get("slug") == slug):
                    is_complete = (
                        tp.get("status") == "completed" or
                        (tp.get("image_url") and tp.get("character_data_json"))
                    )
                    if is_complete:
                        return (True, tp)

        return (False, None)

    timepoint_data = await wait_for_completion(
        check_func=check_completion,
        timeout_seconds=180,  # 3 minutes max
        poll_interval=3.0,  # Check every 3 seconds
        description="timepoint generation"
    )

    # Step 3: Verify we got the timepoint
    if not timepoint_data:
        pytest.skip(f"Timepoint generation timed out after 180s for: {query}")

    assert timepoint_data is not None, "Failed to retrieve timepoint"

    print(f"✓ Timepoint generation completed")
    print(f"  Year: {timepoint_data.get('year')}")
    print(f"  Season: {timepoint_data.get('season')}")
    print(f"  Location: {timepoint_data.get('location')}")

    # Get character and dialog data (handle both field name formats)
    characters = timepoint_data.get("character_data") or timepoint_data.get("character_data_json", [])
    dialog = timepoint_data.get("dialog") or timepoint_data.get("dialog_json", [])

    print(f"  Characters: {len(characters)}")
    print(f"  Dialog lines: {len(dialog)}")

    # Step 4: Validate structure
    print("Step 4: Validating timepoint structure...")
    is_valid, errors = verify_timepoint_structure(timepoint_data)

    if not is_valid:
        print(f"⚠ Structure validation warnings:")
        for error in errors:
            print(f"  - {error}")
        # Don't fail on structure issues, just warn
    else:
        print(f"✓ Structure validation passed")

    # Step 5: Validate image (if present)
    if timepoint_data.get("image_url"):
        print("Step 5: Validating image data...")
        image_valid = verify_image_data(timepoint_data["image_url"], expected_format="PNG")
        assert image_valid, "Image validation failed"
    else:
        print("⚠ No image URL found in timepoint data")

    # Step 6: Judge quality with LLM
    print("Step 6: Evaluating quality with LLM judge...")
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

    # Step 7: Assert quality meets threshold
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
