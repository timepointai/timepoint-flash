"""Unit tests for visibility + share URL feature.

Tests for:
- TimepointVisibility enum
- timepoint_to_response with visibility/share_url
- Redaction logic for private timepoints
- check_visibility_access helper
- List filtering by visibility

Run with:
    pytest tests/unit/test_visibility.py -v -m fast
"""

import pytest
from unittest.mock import MagicMock, patch

from app.models import Timepoint, TimepointStatus, TimepointVisibility


# ---------------------------------------------------------------------------
# Helpers to build mock-ish Timepoint objects without a real DB
# ---------------------------------------------------------------------------

def _make_timepoint(
    visibility: TimepointVisibility = TimepointVisibility.PUBLIC,
    user_id: str | None = None,
    slug: str = "test-slug-abc123",
    **kwargs,
) -> Timepoint:
    """Build a Timepoint with sensible defaults for testing."""
    import uuid as _uuid

    tp = Timepoint.create(query="test query", slug=slug)
    tp.id = str(_uuid.uuid4())  # Ensure id is always set for tests
    tp.is_deleted = False
    tp.status = TimepointStatus.COMPLETED
    tp.visibility = visibility
    tp.user_id = user_id
    tp.year = 1776
    tp.location = "Philadelphia"
    tp.character_data_json = {"characters": []}
    tp.dialog_json = [{"speaker": "A", "line": "Hello"}]
    tp.scene_data_json = {"setting": "hall"}
    tp.metadata_json = {"key": "value"}
    tp.grounding_data_json = {"verified": True}
    tp.moment_data_json = {"arc": "rising"}
    tp.image_prompt = "A grand hall"
    tp.image_url = "https://example.com/img.png"
    tp.image_base64 = "base64data"
    tp.text_model_used = "gemini-2.5-flash"
    tp.image_model_used = "gemini-2.5-flash-image"
    for k, v in kwargs.items():
        setattr(tp, k, v)
    return tp


def _make_user(user_id: str = "user-1") -> MagicMock:
    """Build a mock User."""
    user = MagicMock()
    user.id = user_id
    user.is_active = True
    return user


# ---------------------------------------------------------------------------
# TimepointVisibility enum
# ---------------------------------------------------------------------------


@pytest.mark.fast
class TestTimepointVisibilityEnum:
    """Test the enum itself."""

    def test_public_value(self):
        assert TimepointVisibility.PUBLIC.value == "public"

    def test_private_value(self):
        assert TimepointVisibility.PRIVATE.value == "private"

    def test_is_string_enum(self):
        assert isinstance(TimepointVisibility.PUBLIC, str)
        assert TimepointVisibility.PUBLIC == "public"

    def test_construct_from_string(self):
        assert TimepointVisibility("public") == TimepointVisibility.PUBLIC
        assert TimepointVisibility("private") == TimepointVisibility.PRIVATE

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            TimepointVisibility("unlisted")


# ---------------------------------------------------------------------------
# check_visibility_access
# ---------------------------------------------------------------------------


@pytest.mark.fast
class TestCheckVisibilityAccess:
    """Tests for the visibility access check helper."""

    def test_public_allows_anonymous(self):
        from app.api.v1.timepoints import check_visibility_access

        tp = _make_timepoint(visibility=TimepointVisibility.PUBLIC)
        # Should not raise
        check_visibility_access(tp, None)

    def test_public_allows_any_user(self):
        from app.api.v1.timepoints import check_visibility_access

        tp = _make_timepoint(visibility=TimepointVisibility.PUBLIC, user_id="owner-1")
        user = _make_user("different-user")
        check_visibility_access(tp, user)

    def test_private_blocks_anonymous(self):
        from fastapi import HTTPException
        from app.api.v1.timepoints import check_visibility_access

        tp = _make_timepoint(visibility=TimepointVisibility.PRIVATE, user_id="owner-1")
        with pytest.raises(HTTPException) as exc_info:
            check_visibility_access(tp, None)
        assert exc_info.value.status_code == 403

    def test_private_blocks_non_owner(self):
        from fastapi import HTTPException
        from app.api.v1.timepoints import check_visibility_access

        tp = _make_timepoint(visibility=TimepointVisibility.PRIVATE, user_id="owner-1")
        user = _make_user("other-user")
        with pytest.raises(HTTPException) as exc_info:
            check_visibility_access(tp, user)
        assert exc_info.value.status_code == 403

    def test_private_allows_owner(self):
        from app.api.v1.timepoints import check_visibility_access

        tp = _make_timepoint(visibility=TimepointVisibility.PRIVATE, user_id="owner-1")
        user = _make_user("owner-1")
        # Should not raise
        check_visibility_access(tp, user)


# ---------------------------------------------------------------------------
# timepoint_to_response — visibility & share_url
# ---------------------------------------------------------------------------


@pytest.mark.fast
class TestTimepointToResponseVisibility:
    """Tests for visibility fields in timepoint_to_response."""

    def test_public_timepoint_has_visibility_field(self):
        from app.api.v1.timepoints import timepoint_to_response

        tp = _make_timepoint()
        resp = timepoint_to_response(tp)
        assert resp.visibility == "public"

    def test_private_timepoint_has_visibility_field(self):
        from app.api.v1.timepoints import timepoint_to_response

        tp = _make_timepoint(visibility=TimepointVisibility.PRIVATE, user_id="u1")
        owner = _make_user("u1")
        resp = timepoint_to_response(tp, current_user=owner)
        assert resp.visibility == "private"

    @patch("app.api.v1.timepoints.get_settings")
    def test_share_url_when_base_configured(self, mock_settings):
        from app.api.v1.timepoints import timepoint_to_response

        settings = MagicMock()
        settings.SHARE_URL_BASE = "https://timepointai.com/t"
        mock_settings.return_value = settings

        tp = _make_timepoint(slug="my-slug-abc123")
        resp = timepoint_to_response(tp)
        assert resp.share_url == "https://timepointai.com/t/my-slug-abc123"

    @patch("app.api.v1.timepoints.get_settings")
    def test_no_share_url_when_base_empty(self, mock_settings):
        from app.api.v1.timepoints import timepoint_to_response

        settings = MagicMock()
        settings.SHARE_URL_BASE = ""
        mock_settings.return_value = settings

        tp = _make_timepoint()
        resp = timepoint_to_response(tp)
        assert resp.share_url is None

    @patch("app.api.v1.timepoints.get_settings")
    def test_no_share_url_for_private(self, mock_settings):
        from app.api.v1.timepoints import timepoint_to_response

        settings = MagicMock()
        settings.SHARE_URL_BASE = "https://timepointai.com/t"
        mock_settings.return_value = settings

        tp = _make_timepoint(visibility=TimepointVisibility.PRIVATE, user_id="u1")
        owner = _make_user("u1")
        resp = timepoint_to_response(tp, current_user=owner)
        assert resp.share_url is None


# ---------------------------------------------------------------------------
# Redaction for private timepoints
# ---------------------------------------------------------------------------


@pytest.mark.fast
class TestPrivateRedaction:
    """Tests that private timepoint data is redacted for non-owners."""

    @patch("app.api.v1.timepoints.get_settings")
    def test_anonymous_sees_redacted_private(self, mock_settings):
        from app.api.v1.timepoints import timepoint_to_response

        settings = MagicMock()
        settings.SHARE_URL_BASE = ""
        mock_settings.return_value = settings

        tp = _make_timepoint(
            visibility=TimepointVisibility.PRIVATE,
            user_id="owner-1",
        )
        resp = timepoint_to_response(tp, include_full=True, current_user=None)

        # Sensitive fields should be None/False
        assert resp.characters is None
        assert resp.dialog is None
        assert resp.scene is None
        assert resp.metadata is None
        assert resp.grounding is None
        assert resp.moment is None
        assert resp.image_base64 is None
        assert resp.image_url is None
        assert resp.image_prompt is None
        assert resp.text_model_used is None
        assert resp.image_model_used is None
        assert resp.has_image is False

        # Non-sensitive fields should still be present
        assert resp.id is not None
        assert resp.query == "test query"
        assert resp.slug is not None
        assert resp.year == 1776
        assert resp.visibility == "private"

    @patch("app.api.v1.timepoints.get_settings")
    def test_non_owner_sees_redacted_private(self, mock_settings):
        from app.api.v1.timepoints import timepoint_to_response

        settings = MagicMock()
        settings.SHARE_URL_BASE = ""
        mock_settings.return_value = settings

        tp = _make_timepoint(
            visibility=TimepointVisibility.PRIVATE,
            user_id="owner-1",
        )
        other = _make_user("other-user")
        resp = timepoint_to_response(tp, include_full=True, current_user=other)

        assert resp.characters is None
        assert resp.dialog is None
        assert resp.image_url is None
        assert resp.has_image is False

    @patch("app.api.v1.timepoints.get_settings")
    def test_owner_sees_full_private(self, mock_settings):
        from app.api.v1.timepoints import timepoint_to_response

        settings = MagicMock()
        settings.SHARE_URL_BASE = ""
        mock_settings.return_value = settings

        tp = _make_timepoint(
            visibility=TimepointVisibility.PRIVATE,
            user_id="owner-1",
        )
        owner = _make_user("owner-1")
        resp = timepoint_to_response(tp, include_full=True, current_user=owner)

        # Owner should see full data
        assert resp.characters is not None
        assert resp.dialog is not None
        assert resp.scene is not None
        assert resp.metadata is not None
        assert resp.grounding is not None
        assert resp.moment is not None
        assert resp.image_url is not None
        assert resp.image_prompt is not None
        assert resp.text_model_used is not None
        assert resp.image_model_used is not None

    @patch("app.api.v1.timepoints.get_settings")
    def test_public_shows_full_data_to_anonymous(self, mock_settings):
        from app.api.v1.timepoints import timepoint_to_response

        settings = MagicMock()
        settings.SHARE_URL_BASE = ""
        mock_settings.return_value = settings

        tp = _make_timepoint(visibility=TimepointVisibility.PUBLIC)
        resp = timepoint_to_response(tp, include_full=True, current_user=None)

        assert resp.characters is not None
        assert resp.dialog is not None
        assert resp.image_url is not None
        assert resp.has_image is True


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


@pytest.mark.fast
class TestTimepointVisibilityDefaults:
    """Test default visibility on new timepoints."""

    def test_create_defaults_to_public(self):
        tp = Timepoint.create(query="test")
        assert tp.visibility == TimepointVisibility.PUBLIC

    def test_create_with_explicit_visibility(self):
        tp = Timepoint.create(query="test")
        tp.visibility = TimepointVisibility.PRIVATE
        assert tp.visibility == TimepointVisibility.PRIVATE

    def test_to_dict_includes_visibility(self):
        tp = Timepoint.create(query="test")
        data = tp.to_dict()
        assert data["visibility"] == "public"

    def test_to_dict_private(self):
        tp = Timepoint.create(query="test")
        tp.visibility = TimepointVisibility.PRIVATE
        data = tp.to_dict()
        assert data["visibility"] == "private"
