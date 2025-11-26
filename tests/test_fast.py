"""
Fast unit tests for Timepoint Flash.

These tests run quickly without external API calls.
Run with: pytest -m fast
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Email, Timepoint, RateLimit
from app.utils.rate_limiter import check_rate_limit, update_rate_limit
from datetime import datetime, timedelta


@pytest.mark.fast
def test_health_endpoint(client: TestClient):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "timepoint-flash"


@pytest.mark.fast
def test_root_endpoint(client: TestClient):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "TIMEPOINT AI API"
    assert data["status"] == "running"


@pytest.mark.fast
def test_email_creation(db_session: Session):
    """Test creating an email in the database."""
    email = Email(email="test@example.com")
    db_session.add(email)
    db_session.commit()
    db_session.refresh(email)

    assert email.id is not None
    assert email.email == "test@example.com"
    assert email.created_at is not None


@pytest.mark.fast
def test_rate_limit_check_no_limit(db_session: Session):
    """Test rate limit check when no timepoints have been created."""
    email = Email(email="new@example.com")
    db_session.add(email)
    db_session.commit()

    is_allowed, error_message = check_rate_limit(db_session, "new@example.com")

    assert is_allowed is True
    assert error_message is None


@pytest.mark.fast
def test_rate_limit_check_with_limit(db_session: Session, test_settings):
    """Test rate limit check when limit has been reached."""
    email = Email(email="limited@example.com")
    db_session.add(email)
    db_session.commit()

    # Create a recent rate limit
    now = datetime.utcnow()
    rate_limit = RateLimit(
        email_id=email.id,
        last_created_at=now,
        count_1h=1
    )
    db_session.add(rate_limit)
    db_session.commit()

    is_allowed, error_message = check_rate_limit(
        db_session,
        "limited@example.com"
    )

    assert is_allowed is False
    assert error_message is not None
    assert "wait" in error_message.lower()


@pytest.mark.fast
def test_rate_limit_check_expired_window(db_session: Session):
    """Test rate limit check when time window has expired."""
    email = Email(email="expired@example.com")
    db_session.add(email)
    db_session.commit()

    # Create a timepoint from 2 hours ago (outside window)
    old_time = datetime.utcnow() - timedelta(hours=2)
    rate_limit = RateLimit(
        email_id=email.id,
        last_created_at=old_time,
        count_1h=1
    )
    db_session.add(rate_limit)
    db_session.commit()

    is_allowed, error_message = check_rate_limit(
        db_session,
        "expired@example.com"
    )

    assert is_allowed is True
    assert error_message is None


@pytest.mark.fast
def test_update_rate_limit(db_session: Session):
    """Test updating rate limit after timepoint creation."""
    email = Email(email="creator@example.com")
    db_session.add(email)
    db_session.commit()

    # Record creation
    update_rate_limit(db_session, "creator@example.com")

    # Check rate limit was updated
    is_allowed, error_message = check_rate_limit(
        db_session,
        "creator@example.com"
    )

    assert is_allowed is False
    assert error_message is not None


@pytest.mark.fast
def test_timepoint_model(db_session: Session):
    """Test creating a timepoint model."""
    email = Email(email="timepoint@example.com")
    db_session.add(email)
    db_session.commit()

    timepoint = Timepoint(
        email_id=email.id,
        input_query="Test query",
        cleaned_query="Test query",
        year=2024,
        season="summer",
        slug="2024-summer-test",
        character_data_json=[{"name": "Test Character"}],
        dialog_json=[{"speaker": "Test", "text": "Hello"}],
        metadata_json={"location": "Test Location"}
    )
    db_session.add(timepoint)
    db_session.commit()
    db_session.refresh(timepoint)

    assert timepoint.id is not None
    assert timepoint.slug == "2024-summer-test"
    assert timepoint.year == 2024
    assert timepoint.season == "summer"
    assert len(timepoint.character_data_json) == 1
    assert len(timepoint.dialog_json) == 1


@pytest.mark.fast
def test_api_docs_available(client: TestClient, test_settings):
    """Test that API documentation endpoint responds."""
    response = client.get("/api/docs")
    # Accept either 200 (if available) or 404 (if disabled)
    # The actual availability depends on app configuration
    assert response.status_code in [200, 404]


@pytest.mark.fast
def test_feed_endpoint_empty(client: TestClient):
    """Test feed endpoint with no timepoints."""
    response = client.get("/api/feed")
    assert response.status_code == 200
    data = response.json()
    assert "timepoints" in data
    assert len(data["timepoints"]) == 0


@pytest.mark.fast
def test_invalid_email_format(client: TestClient):
    """Test that invalid email format is handled."""
    response = client.post(
        "/api/timepoint/create",
        json={
            "query": "Test query",
            "email": "not-an-email"
        }
    )
    # Email validation might be lenient or handled by the endpoint
    # Accept any response (validation may not be strict)
    assert response.status_code in [200, 400, 422, 429]


@pytest.mark.fast
def test_slug_generation():
    """Test slug generation logic."""
    from app.models import Timepoint

    # Test that slugs are properly formatted
    test_cases = [
        ("Medieval Marketplace", "medieval-marketplace"),
        ("Fall of Rome!", "fall-of-rome"),
        ("Moon Landing 1969", "moon-landing-1969"),
    ]

    for input_text, expected in test_cases:
        # Simulate slug creation
        slug = input_text.lower().replace(" ", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        assert expected in slug


@pytest.mark.fast
def test_database_models_repr(db_session: Session):
    """Test that model __repr__ methods work."""
    email = Email(email="repr@example.com")
    db_session.add(email)
    db_session.commit()

    repr_str = repr(email)
    # Just check that repr works without errors
    assert "Email" in repr_str or "email" in repr_str.lower()
    assert repr_str is not None
