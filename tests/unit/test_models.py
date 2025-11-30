"""Unit tests for database models.

Tests for app/models.py - Timepoint and related models.

Run with:
    pytest tests/unit/test_models.py -v
    pytest tests/unit/test_models.py -v -m fast
"""

import pytest

from app.models import GenerationLog, Timepoint, TimepointStatus, generate_slug


@pytest.mark.fast
class TestTimepointStatus:
    """Tests for TimepointStatus enum."""

    def test_status_values(self):
        """Test TimepointStatus has expected values."""
        assert TimepointStatus.PENDING.value == "pending"
        assert TimepointStatus.PROCESSING.value == "processing"
        assert TimepointStatus.COMPLETED.value == "completed"
        assert TimepointStatus.FAILED.value == "failed"

    def test_status_is_string_enum(self):
        """Test TimepointStatus is a string enum."""
        assert isinstance(TimepointStatus.PENDING.value, str)


@pytest.mark.fast
class TestGenerateSlug:
    """Tests for slug generation function."""

    def test_basic_slug(self):
        """Test basic slug generation."""
        slug = generate_slug("Signing of the Declaration")
        assert slug == "signing-of-the-declaration"

    def test_slug_with_year(self):
        """Test slug generation with year."""
        slug = generate_slug("Rome", 50)
        assert slug == "rome-50"

    def test_slug_removes_special_characters(self):
        """Test slug removes special characters."""
        slug = generate_slug("What's happening? Test!")
        assert slug == "whats-happening-test"

    def test_slug_handles_multiple_spaces(self):
        """Test slug handles multiple spaces."""
        slug = generate_slug("Test   Multiple   Spaces")
        assert slug == "test-multiple-spaces"

    def test_slug_is_lowercase(self):
        """Test slug is lowercase."""
        slug = generate_slug("UPPERCASE TEST")
        assert slug == "uppercase-test"

    def test_slug_max_length(self):
        """Test slug is truncated to max length."""
        long_query = "a" * 200
        slug = generate_slug(long_query)
        assert len(slug) <= 100


@pytest.mark.fast
class TestTimepoint:
    """Tests for Timepoint model."""

    def test_timepoint_create_factory(self):
        """Test Timepoint.create factory method."""
        tp = Timepoint.create(query="Rome 50 BCE")
        assert tp.query == "Rome 50 BCE"
        assert tp.slug == "rome-50-bce"
        assert tp.status == TimepointStatus.PENDING

    def test_timepoint_create_with_year(self):
        """Test Timepoint.create with year."""
        tp = Timepoint.create(query="Rome", year=50)
        assert tp.slug == "rome-50"
        assert tp.year == 50

    def test_timepoint_create_with_custom_slug(self):
        """Test Timepoint.create with custom slug."""
        tp = Timepoint.create(query="Test", slug="custom-slug")
        assert tp.slug == "custom-slug"

    def test_timepoint_mark_processing(self):
        """Test mark_processing state transition."""
        tp = Timepoint.create(query="Test")
        assert tp.status == TimepointStatus.PENDING

        tp.mark_processing()
        assert tp.status == TimepointStatus.PROCESSING

    def test_timepoint_mark_completed(self):
        """Test mark_completed state transition."""
        tp = Timepoint.create(query="Test")
        tp.mark_completed()
        assert tp.status == TimepointStatus.COMPLETED

    def test_timepoint_mark_failed(self):
        """Test mark_failed state transition."""
        tp = Timepoint.create(query="Test")
        tp.mark_failed("Test error message")
        assert tp.status == TimepointStatus.FAILED
        assert tp.error_message == "Test error message"

    def test_timepoint_is_complete(self):
        """Test is_complete property."""
        tp = Timepoint.create(query="Test")
        assert tp.is_complete is False

        tp.mark_completed()
        assert tp.is_complete is True

    def test_timepoint_has_image(self):
        """Test has_image property."""
        tp = Timepoint.create(query="Test")
        assert tp.has_image is False

        tp.image_url = "https://example.com/image.png"
        assert tp.has_image is True

    def test_timepoint_to_dict(self, sample_timepoint_data):
        """Test to_dict conversion."""
        tp = Timepoint.create(**sample_timepoint_data)
        data = tp.to_dict()

        assert data["query"] == sample_timepoint_data["query"]
        assert data["year"] == sample_timepoint_data["year"]
        assert data["location"] == sample_timepoint_data["location"]
        assert "id" in data
        assert "status" in data

    def test_timepoint_repr(self):
        """Test __repr__ method."""
        tp = Timepoint.create(query="Test", slug="test-slug")
        repr_str = repr(tp)
        assert "test-slug" in repr_str
        assert "pending" in repr_str

    def test_timepoint_with_all_fields(self, sample_timepoint_data):
        """Test Timepoint with all fields populated."""
        tp = Timepoint.create(**sample_timepoint_data)

        assert tp.year == 1776
        assert tp.month == 7
        assert tp.day == 4
        assert tp.season == "summer"
        assert tp.time_of_day == "afternoon"
        assert tp.location == "Independence Hall, Philadelphia"
        assert tp.metadata_json is not None
        assert tp.character_data_json is not None
        assert tp.scene_data_json is not None
        assert tp.dialog_json is not None


@pytest.mark.fast
class TestGenerationLog:
    """Tests for GenerationLog model."""

    def test_generation_log_creation(self):
        """Test GenerationLog can be created."""
        log = GenerationLog(
            timepoint_id="test-uuid",
            step="judge",
            status="completed",
            model_used="gemini-3-pro-preview",
            provider="google",
            latency_ms=100,
        )
        assert log.step == "judge"
        assert log.status == "completed"
        assert log.latency_ms == 100

    def test_generation_log_with_data(self):
        """Test GenerationLog with input/output data."""
        log = GenerationLog(
            timepoint_id="test-uuid",
            step="timeline",
            status="completed",
            input_data={"query": "test"},
            output_data={"year": 1776},
            token_usage={"input_tokens": 10, "output_tokens": 20},
        )
        assert log.input_data == {"query": "test"}
        assert log.output_data == {"year": 1776}
        assert log.token_usage["input_tokens"] == 10

    def test_generation_log_with_error(self):
        """Test GenerationLog with error."""
        log = GenerationLog(
            timepoint_id="test-uuid",
            step="scene",
            status="failed",
            error_message="API timeout",
        )
        assert log.status == "failed"
        assert log.error_message == "API timeout"

    def test_generation_log_repr(self):
        """Test __repr__ method."""
        log = GenerationLog(
            timepoint_id="test-uuid",
            step="judge",
            status="completed",
        )
        repr_str = repr(log)
        assert "judge" in repr_str
        assert "completed" in repr_str
