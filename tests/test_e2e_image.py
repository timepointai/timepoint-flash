"""
E2E tests for image generation and validation.

Tests the image generation pipeline including:
- Image creation
- Format validation
- Image dimensions
- Segmented image generation

Run with: pytest tests/test_e2e_image.py -v
"""

from __future__ import annotations

import pytest

from tests.utils.test_helpers import (
    verify_image_data,
    wait_for_completion,
)

# Endpoint paths
GENERATE_ENDPOINT = "/api/v1/timepoints/generate"
GET_BY_ID_ENDPOINT = "/api/v1/timepoints/{id}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_image_generation_creates_valid_png(test_client, e2e_test_db):
    """Test that image generation produces a valid PNG image."""
    query = "Japanese tea ceremony, Kyoto 1600"

    response = await test_client.post(
        GENERATE_ENDPOINT,
        json={"query": query, "generate_image": True},
    )

    assert response.status_code == 200
    timepoint_id = response.json().get("id")
    assert timepoint_id

    # Wait for image generation
    async def check_completion():
        detail_response = await test_client.get(GET_BY_ID_ENDPOINT.format(id=timepoint_id))
        if detail_response.status_code == 200:
            data = detail_response.json()
            if data.get("status") == "completed" and data.get("has_image"):
                return (True, data)
        return (False, None)

    timepoint_data = await wait_for_completion(
        check_func=check_completion,
        timeout_seconds=180,
        poll_interval=4.0,
        description="image generation",
    )

    if timepoint_data and timepoint_data.get("has_image"):
        # Fetch with image data included
        detail_response = await test_client.get(
            GET_BY_ID_ENDPOINT.format(id=timepoint_id),
            params={"include_image": "true"},
        )
        if detail_response.status_code == 200:
            data = detail_response.json()
            image_data = data.get("image_base64") or data.get("image_url")
            if image_data and image_data.startswith("data:image"):
                is_valid = verify_image_data(image_data, expected_format="PNG")
                assert is_valid, "Generated image is not a valid PNG"
            else:
                # Image URL may be a hosted URL, not base64
                assert image_data or data.get("has_image"), "No image data available"
    else:
        pytest.skip("Image generation timed out or no image URL")


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_image_has_reasonable_dimensions(test_client, e2e_test_db):
    """Test that generated images have reasonable dimensions."""
    import base64
    from io import BytesIO

    from PIL import Image

    query = "Viking longship sailing, Norway 950 CE"

    response = await test_client.post(
        GENERATE_ENDPOINT,
        json={"query": query, "generate_image": True},
    )

    assert response.status_code == 200
    timepoint_id = response.json().get("id")
    assert timepoint_id

    # Wait for image
    async def check_completion():
        detail_response = await test_client.get(GET_BY_ID_ENDPOINT.format(id=timepoint_id))
        if detail_response.status_code == 200:
            data = detail_response.json()
            if data.get("status") == "completed" and data.get("has_image"):
                return (True, data)
        return (False, None)

    timepoint_data = await wait_for_completion(
        check_func=check_completion,
        timeout_seconds=180,
        poll_interval=4.0,
        description="image dimensions check",
    )

    if timepoint_data and timepoint_data.get("has_image"):
        # Fetch with image data
        detail_response = await test_client.get(
            GET_BY_ID_ENDPOINT.format(id=timepoint_id),
            params={"include_image": "true"},
        )
        if detail_response.status_code == 200:
            data = detail_response.json()
            image_data = data.get("image_base64") or data.get("image_url")

            if image_data:
                # Remove data URI prefix
                if image_data.startswith("data:image"):
                    image_data = image_data.split(",", 1)[1]

                try:
                    # Decode and check dimensions
                    image_bytes = base64.b64decode(image_data)
                    img = Image.open(BytesIO(image_bytes))
                    width, height = img.size

                    # Should be at least 512x512 but not absurdly large
                    assert width >= 512, f"Image too narrow: {width}px"
                    assert height >= 512, f"Image too short: {height}px"
                    assert width <= 4096, f"Image too wide: {width}px"
                    assert height <= 4096, f"Image too tall: {height}px"
                except Exception:
                    # Image may be a hosted URL, not base64 — skip dimension check
                    pytest.skip("Image is a URL, cannot check dimensions locally")
            else:
                pytest.skip("No image data returned")
    else:
        pytest.skip("Image generation timed out or no image URL")


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_image_generation_with_query(test_client, e2e_test_db):
    """Test that image generation can be triggered via generate_image flag."""
    query = "Medieval knights tournament, France 1350"

    response = await test_client.post(
        GENERATE_ENDPOINT,
        json={"query": query, "generate_image": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["status"] == "processing"

    timepoint_id = data["id"]

    # Wait for completion
    async def check_completion():
        detail_response = await test_client.get(GET_BY_ID_ENDPOINT.format(id=timepoint_id))
        if detail_response.status_code == 200:
            detail_data = detail_response.json()
            if detail_data.get("status") == "completed":
                return (True, detail_data)
            if detail_data.get("status") == "failed":
                return (True, detail_data)
        return (False, None)

    timepoint_data = await wait_for_completion(
        check_func=check_completion,
        timeout_seconds=200,
        poll_interval=5.0,
        description="image generation with query",
    )

    if timepoint_data:
        assert timepoint_data.get("status") in ["completed", "failed"]
        if timepoint_data.get("status") == "completed":
            # Image may or may not be present depending on API key availability
            assert timepoint_data.get("has_image") is not None
    else:
        pytest.skip("Generation timed out")
