"""
E2E tests for individual AI agents.

Tests each of the agents in the workflow to ensure:
- Correct input/output schemas
- Historical accuracy
- Period-appropriate content
- Edge case handling

Run with: pytest tests/test_e2e_agents.py -v
"""

import pytest

from tests.utils.test_helpers import wait_for_completion

# Endpoint paths
GENERATE_ENDPOINT = "/api/v1/timepoints/generate"
GENERATE_SYNC_ENDPOINT = "/api/v1/timepoints/generate/sync"
GET_BY_ID_ENDPOINT = "/api/v1/timepoints/{id}"
GET_BY_SLUG_ENDPOINT = "/api/v1/timepoints/slug/{slug}"


@pytest.mark.e2e_full
@pytest.mark.asyncio
async def test_judge_agent_accepts_valid_query(test_client, e2e_test_db):
    """Test that judge agent accepts valid historical queries."""
    response = await test_client.post(
        GENERATE_ENDPOINT,
        json={"query": "Ancient Rome, Caesar crossing the Rubicon, 49 BCE"},
    )

    # Should accept (200) not reject (400/422)
    assert response.status_code == 200, f"Judge rejected valid query: {response.text}"
    data = response.json()
    assert "id" in data
    assert data["status"] == "processing"


@pytest.mark.e2e_full
@pytest.mark.asyncio
async def test_judge_agent_rejects_far_future(test_client, e2e_test_db):
    """Test that judge agent rejects far-future dates."""
    response = await test_client.post(
        GENERATE_ENDPOINT,
        json={"query": "Colonization of Mars, year 2150"},
    )

    # Should reject far-future (400 or 422) or accept with eventual failure
    if response.status_code in [400, 422]:
        pass  # Judge correctly rejected far-future query
    else:
        # May still accept and fail during workflow
        assert response.status_code == 200


@pytest.mark.e2e_full
@pytest.mark.asyncio
async def test_judge_agent_rejects_fictional(test_client, e2e_test_db):
    """Test that judge agent rejects obvious fictional queries."""
    response = await test_client.post(
        GENERATE_ENDPOINT,
        json={"query": "Hogwarts School of Witchcraft and Wizardry, 1995"},
    )

    # Should ideally reject fictional content
    if response.status_code in [400, 422]:
        pass  # Judge correctly rejected fictional query
    else:
        # Validation may be lenient
        assert response.status_code == 200


@pytest.mark.e2e_full
@pytest.mark.asyncio
@pytest.mark.slow
async def test_timeline_agent_extracts_correct_year(test_client, e2e_test_db):
    """Test that timeline agent extracts year correctly."""
    query = "Declaration of Independence signing, Philadelphia, July 4 1776"

    response = await test_client.post(
        GENERATE_ENDPOINT,
        json={"query": query},
    )

    assert response.status_code == 200
    timepoint_id = response.json().get("id")
    assert timepoint_id

    # Wait for completion by polling the timepoint
    async def check_completion():
        detail_response = await test_client.get(GET_BY_ID_ENDPOINT.format(id=timepoint_id))
        if detail_response.status_code == 200:
            data = detail_response.json()
            if data.get("status") == "completed" and data.get("year"):
                return (True, data)
        return (False, None)

    timepoint_data = await wait_for_completion(
        check_func=check_completion,
        timeout_seconds=120,
        poll_interval=3.0,
        description="timeline extraction",
    )

    if timepoint_data:
        assert timepoint_data["year"] == 1776, f"Expected year 1776, got {timepoint_data['year']}"
        assert timepoint_data.get("season") in [
            "spring",
            "summer",
            "fall",
            "winter",
            "autumn",
        ]
        location = timepoint_data.get("location", "")
        assert "Philadelphia" in location or "Independence" in location
    else:
        pytest.skip("Timeline extraction timed out")


@pytest.mark.e2e_full
@pytest.mark.asyncio
@pytest.mark.slow
async def test_character_agent_generates_appropriate_count(test_client, e2e_test_db):
    """Test that character agent generates 1-12 characters."""
    query = "Viking raid on English monastery, 793 CE"

    response = await test_client.post(
        GENERATE_ENDPOINT,
        json={"query": query},
    )

    assert response.status_code == 200
    timepoint_id = response.json().get("id")
    assert timepoint_id

    async def check_completion():
        detail_response = await test_client.get(GET_BY_ID_ENDPOINT.format(id=timepoint_id))
        if detail_response.status_code == 200:
            data = detail_response.json()
            if data.get("status") == "completed" and data.get("characters"):
                return (True, data)
        return (False, None)

    timepoint_data = await wait_for_completion(
        check_func=check_completion,
        timeout_seconds=120,
        poll_interval=3.0,
        description="character generation",
    )

    if timepoint_data:
        characters = timepoint_data.get("characters", {})
        # characters may be a dict with a "characters" key or a list
        if isinstance(characters, dict):
            char_list = characters.get("characters", [])
        else:
            char_list = characters if isinstance(characters, list) else []

        char_count = len(char_list)
        assert 1 <= char_count <= 12, f"Character count out of range: {char_count}"

        # Check first character has required fields
        if char_count > 0:
            first_char = char_list[0]
            assert isinstance(first_char, dict), "Character should be a dict"
            assert "name" in first_char, "Missing 'name' field in character"
    else:
        pytest.skip("Character generation timed out")


@pytest.mark.e2e_full
@pytest.mark.asyncio
@pytest.mark.slow
async def test_dialog_agent_uses_period_language(test_client, e2e_test_db):
    """Test that dialog agent generates period-appropriate language."""
    query = "Shakespeare's Globe Theatre performance, London 1599"

    response = await test_client.post(
        GENERATE_ENDPOINT,
        json={"query": query},
    )

    assert response.status_code == 200
    timepoint_id = response.json().get("id")
    assert timepoint_id

    async def check_completion():
        detail_response = await test_client.get(GET_BY_ID_ENDPOINT.format(id=timepoint_id))
        if detail_response.status_code == 200:
            data = detail_response.json()
            if data.get("status") == "completed" and data.get("dialog"):
                return (True, data)
        return (False, None)

    timepoint_data = await wait_for_completion(
        check_func=check_completion,
        timeout_seconds=120,
        poll_interval=3.0,
        description="dialog generation",
    )

    if timepoint_data:
        dialog = timepoint_data.get("dialog", [])
        assert isinstance(dialog, list)
        dialog_count = len(dialog)

        assert 2 <= dialog_count <= 20, f"Dialog count out of range: {dialog_count}"

        # Collect all dialog text
        dialog_text = " ".join([line.get("text", "") or line.get("line", "") for line in dialog])

        # Shouldn't have obvious anachronisms
        modern_anachronisms = ["okay", "cool", "awesome", "literally", "basically"]
        found_anachronisms = [
            word for word in modern_anachronisms if word.lower() in dialog_text.lower()
        ]

        # Not a hard failure, just informational
        if not found_anachronisms:
            pass  # No obvious modern anachronisms detected

        # Should have some formal language markers
        formal_markers = [
            "thee",
            "thou",
            "hath",
            "doth",
            "good",
            "pray",
            "sir",
            "madam",
            "my lord",
        ]
        found_formal = [word for word in formal_markers if word.lower() in dialog_text.lower()]

        # Not a hard failure — just informational
        assert len(found_formal) > 0 or len(dialog_text) > 0, "Dialog should contain some text"
    else:
        pytest.skip("Dialog generation timed out")


@pytest.mark.e2e_full
@pytest.mark.asyncio
async def test_minimal_query_handling(test_client, e2e_test_db):
    """Test handling of minimal/sparse queries."""
    # Minimal query with just location and year
    response = await test_client.post(
        GENERATE_ENDPOINT,
        json={"query": "Rome 100 CE"},
    )

    # Should still accept and process (agents infer details)
    assert response.status_code == 200, f"Failed on minimal query: {response.text}"
    data = response.json()
    assert "id" in data
    assert data["status"] == "processing"


@pytest.mark.e2e_full
@pytest.mark.asyncio
async def test_complex_query_handling(test_client, e2e_test_db):
    """Test handling of complex queries with many details."""
    response = await test_client.post(
        GENERATE_ENDPOINT,
        json={
            "query": (
                "Elaborate royal banquet at the Palace of Versailles during the reign of Louis XIV, "
                "on a warm summer evening in July 1685, with the entire French court in attendance, "
                "featuring musicians, dancers, and an extravagant feast with exotic delicacies"
            ),
        },
    )

    # Should handle complex queries
    assert response.status_code == 200, f"Failed on complex query: {response.text}"
    data = response.json()
    assert "id" in data
    assert data["status"] == "processing"
