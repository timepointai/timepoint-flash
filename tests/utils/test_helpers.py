"""
Test helper utilities for e2e testing.

Provides shared functions for:
- Smart polling/waiting for async operations
- Image data validation
- Timepoint structure verification
- Test data cleanup
"""
import asyncio
import base64
import time
from typing import Dict, Any, Optional, Callable, Awaitable
from io import BytesIO
from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


async def wait_for_completion(
    check_func: Callable[[], Awaitable[tuple[bool, Optional[Any]]]],
    timeout_seconds: int = 120,
    poll_interval: float = 2.0,
    description: str = "operation"
) -> Optional[Any]:
    """
    Smart polling helper that waits for an async operation to complete.

    Args:
        check_func: Async function that returns (is_complete: bool, result: Any)
        timeout_seconds: Maximum time to wait (default: 120s / 2 minutes)
        poll_interval: Time between checks in seconds (default: 2s)
        description: Human-readable description for logging

    Returns:
        The result from check_func when complete, or None if timeout

    Example:
        async def check_timepoint():
            response = client.get(f"/api/timepoint/details/{slug}")
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "completed":
                    return (True, data)
            return (False, None)

        result = await wait_for_completion(check_timepoint, timeout_seconds=180)
    """
    start_time = time.time()
    attempts = 0

    while time.time() - start_time < timeout_seconds:
        attempts += 1
        elapsed = time.time() - start_time

        # Check if complete
        is_complete, result = await check_func()

        if is_complete:
            print(f"✓ {description} completed after {elapsed:.1f}s ({attempts} attempts)")
            return result

        # Log progress
        if attempts % 5 == 0:  # Log every 10 seconds (5 * 2s interval)
            print(f"  Waiting for {description}... {elapsed:.1f}s elapsed ({attempts} attempts)")

        # Wait before next check
        await asyncio.sleep(poll_interval)

    # Timeout
    print(f"✗ {description} timed out after {timeout_seconds}s ({attempts} attempts)")
    return None


def verify_image_data(image_data: str, expected_format: str = "PNG") -> bool:
    """
    Verify that image data is valid base64-encoded image.

    Args:
        image_data: Base64-encoded image string (may include data URI prefix)
        expected_format: Expected image format (PNG, JPEG, etc.)

    Returns:
        True if valid image, False otherwise
    """
    try:
        # Remove data URI prefix if present
        if image_data.startswith("data:image"):
            # Format: data:image/png;base64,<base64_data>
            image_data = image_data.split(",", 1)[1]

        # Decode base64
        image_bytes = base64.b64decode(image_data)

        # Try to load as image
        img = Image.open(BytesIO(image_bytes))

        # Verify format
        if img.format != expected_format:
            print(f"⚠ Image format mismatch: expected {expected_format}, got {img.format}")
            return False

        # Verify dimensions (reasonable size)
        width, height = img.size
        if width < 100 or height < 100:
            print(f"⚠ Image too small: {width}x{height}")
            return False

        if width > 5000 or height > 5000:
            print(f"⚠ Image too large: {width}x{height}")
            return False

        print(f"✓ Valid {img.format} image: {width}x{height}")
        return True

    except Exception as e:
        print(f"✗ Image validation failed: {e}")
        return False


def verify_timepoint_structure(timepoint_data: Dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Verify that a timepoint has the expected data structure.

    Args:
        timepoint_data: Timepoint dictionary from API

    Returns:
        Tuple of (is_valid: bool, errors: list[str])
    """
    errors = []

    # Required top-level fields
    required_fields = [
        "id", "slug", "year", "season", "input_query", "cleaned_query"
    ]

    for field in required_fields:
        if field not in timepoint_data:
            errors.append(f"Missing required field: {field}")

    # Check data types
    if "year" in timepoint_data:
        if not isinstance(timepoint_data["year"], int):
            errors.append(f"Invalid year type: {type(timepoint_data['year'])}")
        elif timepoint_data["year"] < -10000 or timepoint_data["year"] > 2024:
            errors.append(f"Year out of range: {timepoint_data['year']}")

    if "season" in timepoint_data:
        valid_seasons = ["spring", "summer", "fall", "winter", "autumn"]
        if timepoint_data["season"].lower() not in valid_seasons:
            errors.append(f"Invalid season: {timepoint_data['season']}")

    # Check character data
    if "character_data" in timepoint_data or "character_data_json" in timepoint_data:
        characters = timepoint_data.get("character_data") or timepoint_data.get("character_data_json", [])
        if not isinstance(characters, list):
            errors.append(f"Invalid character_data type: {type(characters)}")
        elif len(characters) == 0:
            errors.append("No characters generated")
        elif len(characters) > 12:
            errors.append(f"Too many characters: {len(characters)}")
        else:
            # Verify character structure
            for i, char in enumerate(characters[:3]):  # Check first 3
                if not isinstance(char, dict):
                    errors.append(f"Character {i} is not a dict: {type(char)}")
                    continue

                required_char_fields = ["name", "role", "appearance", "clothing"]
                for field in required_char_fields:
                    if field not in char:
                        errors.append(f"Character {i} missing field: {field}")

    # Check dialog
    if "dialog" in timepoint_data or "dialog_json" in timepoint_data:
        dialog = timepoint_data.get("dialog") or timepoint_data.get("dialog_json", [])
        if not isinstance(dialog, list):
            errors.append(f"Invalid dialog type: {type(dialog)}")
        elif len(dialog) == 0:
            errors.append("No dialog generated")
        elif len(dialog) > 20:
            errors.append(f"Too many dialog lines: {len(dialog)}")
        else:
            # Verify dialog structure
            for i, line in enumerate(dialog[:3]):  # Check first 3
                if not isinstance(line, dict):
                    errors.append(f"Dialog line {i} is not a dict: {type(line)}")
                    continue

                if "speaker" not in line or "text" not in line:
                    errors.append(f"Dialog line {i} missing speaker or text")

    # Check image (if present)
    if "image_url" in timepoint_data and timepoint_data["image_url"]:
        if not timepoint_data["image_url"].startswith("data:image"):
            errors.append(f"Invalid image_url format: {timepoint_data['image_url'][:50]}")

    is_valid = len(errors) == 0
    return (is_valid, errors)


def cleanup_test_data(
    db_session: Session,
    email_pattern: str = "test-%@example.com"
):
    """
    Clean up test data from database.

    Args:
        db_session: Database session
        email_pattern: Pattern to match test emails (SQL LIKE pattern)
    """
    from app.models import Email, Timepoint, RateLimit, ProcessingSession, IPRateLimit

    try:
        # Delete in reverse dependency order

        # Delete processing sessions for test emails
        test_emails = db_session.query(Email).filter(Email.email.like(email_pattern)).all()
        test_email_ids = [e.id for e in test_emails]

        if test_email_ids:
            # Delete timepoints
            db_session.query(Timepoint).filter(Timepoint.email_id.in_(test_email_ids)).delete(
                synchronize_session=False
            )

            # Delete processing sessions (via email field, not FK)
            for email_obj in test_emails:
                db_session.query(ProcessingSession).filter(
                    ProcessingSession.email == email_obj.email
                ).delete(synchronize_session=False)

            # Delete rate limits
            db_session.query(RateLimit).filter(RateLimit.email_id.in_(test_email_ids)).delete(
                synchronize_session=False
            )

            # Delete emails
            db_session.query(Email).filter(Email.id.in_(test_email_ids)).delete(
                synchronize_session=False
            )

        # Delete test IP rate limits (test IPs typically start with 127.0.0 or testclient)
        db_session.query(IPRateLimit).filter(
            IPRateLimit.ip_address.like("127.0.%")
        ).delete(synchronize_session=False)

        db_session.query(IPRateLimit).filter(
            IPRateLimit.ip_address.like("testclient%")
        ).delete(synchronize_session=False)

        db_session.commit()
        print(f"✓ Cleaned up test data matching pattern: {email_pattern}")

    except Exception as e:
        db_session.rollback()
        print(f"⚠ Cleanup failed: {e}")


def generate_unique_test_email(base: str = "test", domain: str = "example.com") -> str:
    """
    Generate a unique test email address using timestamp.

    Args:
        base: Base name for email (default: "test")
        domain: Email domain (default: "example.com")

    Returns:
        Unique email address like "test-1234567890@example.com"
    """
    import time
    timestamp = int(time.time() * 1000)  # Millisecond precision
    return f"{base}-{timestamp}@{domain}"
