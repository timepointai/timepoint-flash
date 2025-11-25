"""
Fast unit tests for Timepoint Flash.

These tests run quickly without external API calls.
Run with: pytest -m fast
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Email, Timepoint, RateLimit
from app.utils.rate_limiter import check_rate_limit, record_timepoint_creation
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

    available, seconds_remaining = check_rate_limit(db_session, "new@example.com")

    assert available is True
    assert seconds_remaining == 0


@pytest.mark.fast
def test_rate_limit_check_with_limit(db_session: Session, test_settings):
    """Test rate limit check when limit has been reached."""
    email = Email(email="limited@example.com")
    db_session.add(email)
    db_session.commit()

    # Create a recent timepoint
    now = datetime.utcnow()
    rate_limit = RateLimit(
        email_id=email.id,
        timepoints_created=1,
        window_start=now
    )
    db_session.add(rate_limit)
    db_session.commit()

    available, seconds_remaining = check_rate_limit(
        db_session,
        "limited@example.com",
        max_per_hour=1
    )

    assert available is False
    assert seconds_remaining > 0
    assert seconds_remaining <= 3600


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
        timepoints_created=1,
        window_start=old_time
    )
    db_session.add(rate_limit)
    db_session.commit()

    available, seconds_remaining = check_rate_limit(
        db_session,
        "expired@example.com",
        max_per_hour=1
    )

    assert available is True
    assert seconds_remaining == 0


@pytest.mark.fast
def test_record_timepoint_creation(db_session: Session):
    """Test recording a timepoint creation."""
    email = Email(email="creator@example.com")
    db_session.add(email)
    db_session.commit()

    # Record creation
    record_timepoint_creation(db_session, "creator@example.com")

    # Check rate limit was updated
    available, seconds_remaining = check_rate_limit(
        db_session,
        "creator@example.com",
        max_per_hour=1
    )

    assert available is False
    assert seconds_remaining > 0


@pytest.mark.fast
def test_timepoint_model(db_session: Session):
    """Test creating a timepoint model."""
    email = Email(email="timepoint@example.com")
    db_session.add(email)
    db_session.commit()

    timepoint = Timepoint(
        email_id=email.id,
        query="Test query",
        cleaned_query="Test query",
        year=2024,
        season="summer",
        slug="2024-summer-test",
        location="Test Location",
        character_data=[{"name": "Test Character"}],
        dialog=[{"speaker": "Test", "text": "Hello"}],
        status="completed"
    )
    db_session.add(timepoint)
    db_session.commit()
    db_session.refresh(timepoint)

    assert timepoint.id is not None
    assert timepoint.slug == "2024-summer-test"
    assert timepoint.year == 2024
    assert timepoint.season == "summer"
    assert len(timepoint.character_data) == 1
    assert len(timepoint.dialog) == 1


@pytest.mark.fast
def test_api_docs_available(client: TestClient, test_settings):
    """Test that API documentation is available in debug mode."""
    if test_settings.DEBUG:
        response = client.get("/api/docs")
        assert response.status_code == 200


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
    """Test that invalid email format is rejected."""
    response = client.post(
        "/api/timepoint/create",
        json={
            "query": "Test query",
            "email": "not-an-email"
        }
    )
    # Should fail validation
    assert response.status_code in [400, 422]


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
    assert "Email" in repr_str
    assert "repr@example.com" in repr_str
