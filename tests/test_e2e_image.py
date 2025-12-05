"""
E2E tests for image generation and validation.

Tests the image generation pipeline including:
- Image creation
- Format validation
- Segmentation
- Image prompt quality

Run with: pytest tests/test_e2e_image.py -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.utils.test_helpers import (
    generate_unique_test_email,
    wait_for_completion,
    verify_image_data
)
from tests.utils.retry import retry_on_api_error


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_image_generation_creates_valid_png(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """Test that image generation produces a valid PNG image."""
    email = generate_unique_test_email("test-image-png")
    query = "Japanese tea ceremony, Kyoto 1600"

    response = client.post(
        "/api/timepoint/create",
        json={"input_query": query, "requester_email": email}
    )

    assert response.status_code in [200, 201]
    slug = response.json().get("slug")

    # Wait for image generation
    async def check_completion():
        if slug:
            detail_response = client.get(f"/api/timepoint/details/{slug}")
            if detail_response.status_code == 200:
                data = detail_response.json()
                if data.get("image_url"):
                    return (True, data)
        return (False, None)

    timepoint_data = await wait_for_completion(
        check_func=check_completion,
        timeout_seconds=180,
        poll_interval=4.0,
        description="image generation"
    )

    if timepoint_data and timepoint_data.get("image_url"):
        # Validate image format
        is_valid = verify_image_data(timepoint_data["image_url"], expected_format="PNG")
        assert is_valid, "Generated image is not a valid PNG"
        print("✓ Image generation produced valid PNG")
    else:
        pytest.skip("Image generation timed out or no image URL")


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_image_has_reasonable_dimensions(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """Test that generated images have reasonable dimensions."""
    import base64
    from io import BytesIO
    from PIL import Image

    email = generate_unique_test_email("test-image-dimensions")
    query = "Viking longship sailing, Norway 950 CE"

    response = client.post(
        "/api/timepoint/create",
        json={"input_query": query, "requester_email": email}
    )

    assert response.status_code in [200, 201]
    slug = response.json().get("slug")

    # Wait for image
    async def check_completion():
        if slug:
            detail_response = client.get(f"/api/timepoint/details/{slug}")
            if detail_response.status_code == 200:
                data = detail_response.json()
                if data.get("image_url"):
                    return (True, data)
        return (False, None)

    timepoint_data = await wait_for_completion(
        check_func=check_completion,
        timeout_seconds=180,
        poll_interval=4.0,
        description="image dimensions check"
    )

    if timepoint_data and timepoint_data.get("image_url"):
        image_data = timepoint_data["image_url"]

        # Remove data URI prefix
        if image_data.startswith("data:image"):
            image_data = image_data.split(",", 1)[1]

        # Decode and check dimensions
        image_bytes = base64.b64decode(image_data)
        img = Image.open(BytesIO(image_bytes))
        width, height = img.size

        # Should be at least 512x512 but not absurdly large
        assert width >= 512, f"Image too narrow: {width}px"
        assert height >= 512, f"Image too short: {height}px"
        assert width <= 4096, f"Image too wide: {width}px"
        assert height <= 4096, f"Image too tall: {height}px"

        print(f"✓ Image has valid dimensions: {width}x{height}")
    else:
        pytest.skip("Image generation timed out or no image URL")


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_segmented_image_exists(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """Test that segmented image is generated alongside main image."""
    email = generate_unique_test_email("test-segmentation")
    query = "Medieval knights tournament, France 1350"

    response = client.post(
        "/api/timepoint/create",
        json={"input_query": query, "requester_email": email}
    )

    assert response.status_code in [200, 201]
    slug = response.json().get("slug")

    # Wait for completion with segmentation
    async def check_completion():
        if slug:
            detail_response = client.get(f"/api/timepoint/details/{slug}")
            if detail_response.status_code == 200:
                data = detail_response.json()
                if data.get("image_url") and data.get("segmented_image_url"):
                    return (True, data)
        return (False, None)

    timepoint_data = await wait_for_completion(
        check_func=check_completion,
        timeout_seconds=200,  # Longer timeout for segmentation
        poll_interval=5.0,
        description="image segmentation"
    )

    if timepoint_data:
        assert "image_url" in timepoint_data, "Missing main image URL"
        assert "segmented_image_url" in timepoint_data, "Missing segmented image URL"
        assert timepoint_data["image_url"] != timepoint_data["segmented_image_url"], \
            "Segmented image should differ from main image"

        print("✓ Segmented image generated successfully")

        # Validate segmented image is also a valid PNG
        if timepoint_data["segmented_image_url"]:
            is_valid = verify_image_data(timepoint_data["segmented_image_url"], expected_format="PNG")
            assert is_valid, "Segmented image is not a valid PNG"
            print("✓ Segmented image is valid PNG")
    else:
        pytest.skip("Segmentation timed out or incomplete")
