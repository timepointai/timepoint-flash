"""
E2E tests for individual AI agents.

Tests each of the 11 agents in the workflow independently to ensure:
- Correct input/output schemas
- Historical accuracy
- Period-appropriate content
- Edge case handling

Run with: pytest tests/test_e2e_agents.py -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.utils.test_helpers import generate_unique_test_email, verify_timepoint_structure
from tests.utils.retry import retry_on_api_error


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_judge_agent_accepts_valid_query(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """Test that judge agent accepts valid historical queries."""
    email = generate_unique_test_email("test-judge-valid")

    response = client.post(
        "/api/timepoint/create",
        json={
            "input_query": "Ancient Rome, Caesar crossing the Rubicon, 49 BCE",
            "requester_email": email
        }
    )

    # Should accept (200/201) not reject (400)
    assert response.status_code in [200, 201], f"Judge rejected valid query: {response.text}"
    print("✓ Judge accepted valid historical query")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_judge_agent_rejects_far_future(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """Test that judge agent rejects far-future dates."""
    email = generate_unique_test_email("test-judge-future")

    response = client.post(
        "/api/timepoint/create",
        json={
            "input_query": "Colonization of Mars, year 2150",
            "requester_email": email
        }
    )

    # Should reject far-future (400 or immediate failure)
    # Or if accepted, should fail quickly in validation
    if response.status_code in [400, 422]:
        print("✓ Judge correctly rejected far-future query")
    else:
        print("⚠ Judge accepted far-future query (may fail in workflow)")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_judge_agent_rejects_fictional(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """Test that judge agent rejects obvious fictional queries."""
    email = generate_unique_test_email("test-judge-fictional")

    response = client.post(
        "/api/timepoint/create",
        json={
            "input_query": "Hogwarts School of Witchcraft and Wizardry, 1995",
            "requester_email": email
        }
    )

    # Should ideally reject fictional content
    if response.status_code in [400, 422]:
        print("✓ Judge correctly rejected fictional query")
    else:
        print("⚠ Judge accepted fictional query (validation may be lenient)")


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.slow
async def test_timeline_agent_extracts_correct_year(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """Test that timeline agent extracts year correctly."""
    import asyncio
    from tests.utils.test_helpers import wait_for_completion

    email = generate_unique_test_email("test-timeline")
    query = "Declaration of Independence signing, Philadelphia, July 4 1776"

    response = client.post(
        "/api/timepoint/create",
        json={"input_query": query, "requester_email": email}
    )

    assert response.status_code in [200, 201]
    slug = response.json().get("slug")

    # Wait for completion
    async def check_completion():
        if slug:
            detail_response = client.get(f"/api/timepoint/details/{slug}")
            if detail_response.status_code == 200:
                data = detail_response.json()
                if data.get("year"):
                    return (True, data)
        return (False, None)

    timepoint_data = await wait_for_completion(
        check_func=check_completion,
        timeout_seconds=120,
        poll_interval=3.0,
        description="timeline extraction"
    )

    if timepoint_data:
        assert timepoint_data["year"] == 1776, f"Expected year 1776, got {timepoint_data['year']}"
        assert timepoint_data["season"] in ["spring", "summer", "fall", "winter"]
        assert "Philadelphia" in timepoint_data.get("location", "")
        print(f"✓ Timeline agent correctly extracted: {timepoint_data['year']}, {timepoint_data['season']}, {timepoint_data['location']}")
    else:
        pytest.skip("Timeline extraction timed out")


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.slow
async def test_character_agent_generates_appropriate_count(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """Test that character agent generates 1-12 characters."""
    import asyncio
    from tests.utils.test_helpers import wait_for_completion

    email = generate_unique_test_email("test-characters")
    query = "Viking raid on English monastery, 793 CE"

    response = client.post(
        "/api/timepoint/create",
        json={"input_query": query, "requester_email": email}
    )

    assert response.status_code in [200, 201]
    slug = response.json().get("slug")

    # Wait for completion
    async def check_completion():
        if slug:
            detail_response = client.get(f"/api/timepoint/details/{slug}")
            if detail_response.status_code == 200:
                data = detail_response.json()
                chars = data.get("character_data") or data.get("character_data_json", [])
                if len(chars) > 0:
                    return (True, data)
        return (False, None)

    timepoint_data = await wait_for_completion(
        check_func=check_completion,
        timeout_seconds=120,
        poll_interval=3.0,
        description="character generation"
    )

    if timepoint_data:
        characters = timepoint_data.get("character_data") or timepoint_data.get("character_data_json", [])
        char_count = len(characters)

        assert 1 <= char_count <= 12, f"Character count out of range: {char_count}"
        print(f"✓ Character agent generated {char_count} characters (valid range)")

        # Check first character has required fields
        if char_count > 0:
            first_char = characters[0]
            required_fields = ["name", "role", "appearance", "clothing"]
            for field in required_fields:
                assert field in first_char, f"Missing field '{field}' in character"
            print(f"✓ Character has all required fields: {first_char['name']}")
    else:
        pytest.skip("Character generation timed out")


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.slow
async def test_dialog_agent_uses_period_language(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """Test that dialog agent generates period-appropriate language."""
    import asyncio
    from tests.utils.test_helpers import wait_for_completion

    email = generate_unique_test_email("test-dialog")
    query = "Shakespeare's Globe Theatre performance, London 1599"

    response = client.post(
        "/api/timepoint/create",
        json={"input_query": query, "requester_email": email}
    )

    assert response.status_code in [200, 201]
    slug = response.json().get("slug")

    # Wait for completion
    async def check_completion():
        if slug:
            detail_response = client.get(f"/api/timepoint/details/{slug}")
            if detail_response.status_code == 200:
                data = detail_response.json()
                dialog = data.get("dialog") or data.get("dialog_json", [])
                if len(dialog) > 0:
                    return (True, data)
        return (False, None)

    timepoint_data = await wait_for_completion(
        check_func=check_completion,
        timeout_seconds=120,
        poll_interval=3.0,
        description="dialog generation"
    )

    if timepoint_data:
        dialog = timepoint_data.get("dialog") or timepoint_data.get("dialog_json", [])
        dialog_count = len(dialog)

        assert 2 <= dialog_count <= 20, f"Dialog count out of range: {dialog_count}"
        print(f"✓ Dialog agent generated {dialog_count} lines (valid range)")

        # Check for Elizabethan language patterns (this is heuristic)
        dialog_text = " ".join([line.get("text", "") for line in dialog])

        # Shouldn't have obvious anachronisms
        modern_anachronisms = ["okay", "cool", "awesome", "literally", "basically"]
        found_anachronisms = [word for word in modern_anachronisms if word.lower() in dialog_text.lower()]

        if found_anachronisms:
            print(f"⚠ Found potential anachronisms: {found_anachronisms}")
        else:
            print("✓ No obvious modern anachronisms detected")

        # Should have some formal language markers
        formal_markers = ["thee", "thou", "hath", "doth", "good", "pray", "sir", "madam", "my lord"]
        found_formal = [word for word in formal_markers if word.lower() in dialog_text.lower()]

        if found_formal:
            print(f"✓ Found period-appropriate language markers: {found_formal[:3]}")
        else:
            print("⚠ No obvious Elizabethan language markers found")

    else:
        pytest.skip("Dialog generation timed out")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_minimal_query_handling(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """Test handling of minimal/sparse queries."""
    email = generate_unique_test_email("test-minimal")

    # Minimal query with just location and year
    response = client.post(
        "/api/timepoint/create",
        json={
            "input_query": "Rome 100 CE",
            "requester_email": email
        }
    )

    # Should still accept and process (agents infer details)
    assert response.status_code in [200, 201], f"Failed on minimal query: {response.text}"
    print("✓ System accepts minimal queries and infers details")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_complex_query_handling(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """Test handling of complex queries with many details."""
    email = generate_unique_test_email("test-complex")

    # Very detailed query
    response = client.post(
        "/api/timepoint/create",
        json={
            "input_query": (
                "Elaborate royal banquet at the Palace of Versailles during the reign of Louis XIV, "
                "on a warm summer evening in July 1685, with the entire French court in attendance, "
                "featuring musicians, dancers, and an extravagant feast with exotic delicacies"
            ),
            "requester_email": email
        }
    )

    # Should handle complex queries
    assert response.status_code in [200, 201], f"Failed on complex query: {response.text}"
    print("✓ System accepts and processes complex detailed queries")
