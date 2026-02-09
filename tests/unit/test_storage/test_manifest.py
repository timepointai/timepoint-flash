"""Tests for app.storage.manifest module.

Covers:
    - BlobManifest schema validation
    - FileEntry model
    - build_manifest() from a mock timepoint
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.storage.manifest import (
    BlobManifest,
    FileEntry,
    ProvenanceInfo,
    SequenceInfo,
    TemporalInfo,
    build_manifest,
)


class TestFileEntry:
    """Tests for FileEntry model."""

    def test_basic_creation(self):
        entry = FileEntry(filename="image.png", mime_type="image/png", size_bytes=1234)
        assert entry.filename == "image.png"
        assert entry.mime_type == "image/png"
        assert entry.size_bytes == 1234

    def test_with_sha256(self):
        entry = FileEntry(
            filename="data.json",
            mime_type="application/json",
            size_bytes=100,
            sha256="abc123",
        )
        assert entry.sha256 == "abc123"

    def test_default_size(self):
        entry = FileEntry(filename="x.txt", mime_type="text/plain")
        assert entry.size_bytes == 0


class TestBlobManifest:
    """Tests for BlobManifest model."""

    def test_minimal_creation(self):
        m = BlobManifest(
            timepoint_id="test-id",
            slug="test-slug",
            query="test query",
            folder_name="test_20260209_abc123",
            full_path="/tmp/test",
        )
        assert m.manifest_version == "1.0"
        assert m.timepoint_id == "test-id"
        assert m.render_type == "image"
        assert m.generation_version == 1

    def test_stubs_present(self):
        m = BlobManifest(
            timepoint_id="x",
            slug="x",
            query="x",
            folder_name="x",
            full_path="/x",
        )
        assert "cloud_storage" in m.stubs
        assert m.stubs["cloud_storage"] == "coming soon"
        assert "c2pa_credentials" in m.stubs

    def test_files_list(self):
        m = BlobManifest(
            timepoint_id="x",
            slug="x",
            query="x",
            folder_name="x",
            full_path="/x",
            files=[
                FileEntry(filename="a.png", mime_type="image/png", size_bytes=100),
                FileEntry(filename="b.json", mime_type="application/json", size_bytes=50),
            ],
            total_size_bytes=150,
        )
        assert len(m.files) == 2
        assert m.total_size_bytes == 150

    def test_serialization_roundtrip(self):
        m = BlobManifest(
            timepoint_id="test-id",
            slug="test",
            query="test",
            folder_name="test_20260209_abc",
            full_path="/tmp/test",
        )
        json_str = m.model_dump_json()
        m2 = BlobManifest.model_validate_json(json_str)
        assert m2.timepoint_id == m.timepoint_id
        assert m2.stubs == m.stubs


class TestBuildManifest:
    """Tests for build_manifest() function."""

    def _make_mock_timepoint(self, **overrides):
        tp = MagicMock()
        tp.id = overrides.get("id", "tp-123")
        tp.slug = overrides.get("slug", "test-slug")
        tp.query = overrides.get("query", "test query")
        tp.year = overrides.get("year", 1943)
        tp.month = overrides.get("month", 1)
        tp.era = overrides.get("era", "WWII")
        tp.location = overrides.get("location", "New York")
        tp.text_model_used = overrides.get("text_model_used", "gemini-2.5-flash")
        tp.image_model_used = overrides.get("image_model_used", "gemini-2.5-flash-image")
        tp.created_at = overrides.get("created_at", datetime(2026, 2, 9, tzinfo=timezone.utc))
        tp.parent_id = overrides.get("parent_id", None)
        tp.sequence_id = overrides.get("sequence_id", None)
        tp.nsfw_flag = overrides.get("nsfw_flag", False)
        tp.render_type = overrides.get("render_type", "image")
        tp.created_by = overrides.get("created_by", None)
        tp.api_source = overrides.get("api_source", "api")
        tp.view_count = overrides.get("view_count", 0)
        tp.last_accessed_at = overrides.get("last_accessed_at", None)
        tp.generation_version = overrides.get("generation_version", 1)
        tp.tags_json = overrides.get("tags_json", ["history", "wwii"])
        tp.metadata_json = overrides.get("metadata_json", {})
        return tp

    def test_basic_build(self):
        tp = self._make_mock_timepoint()
        entries = [
            FileEntry(filename="image.png", mime_type="image/png", size_bytes=1000),
        ]
        m = build_manifest(tp, "folder_name", "/full/path", entries)
        assert m.timepoint_id == "tp-123"
        assert m.temporal.year == 1943
        assert m.provenance.text_model == "gemini-2.5-flash"
        assert m.total_size_bytes == 1000

    def test_tags_extracted(self):
        tp = self._make_mock_timepoint(tags_json=["tag1", "tag2"])
        m = build_manifest(tp, "f", "/p", [])
        assert m.tags == ["tag1", "tag2"]

    def test_sequence_info(self):
        tp = self._make_mock_timepoint(sequence_id="seq-001", parent_id="parent-001")
        m = build_manifest(tp, "f", "/p", [])
        assert m.sequence.sequence_id == "seq-001"
        assert m.sequence.parent_timepoint_id == "parent-001"

    def test_synthetic_camera(self):
        tp = self._make_mock_timepoint(
            metadata_json={"synthetic_camera": {"{synthetic}shot_type": "wide"}}
        )
        m = build_manifest(tp, "f", "/p", [])
        assert m.synthetic_camera.get("{synthetic}shot_type") == "wide"

    def test_generation_logs_steps(self):
        tp = self._make_mock_timepoint()
        entries = [FileEntry(filename="a.json", mime_type="application/json", size_bytes=10)]
        m = build_manifest(
            tp, "f", "/p", entries,
            generation_log_steps=["judge", "timeline", "scene"],
            total_latency_ms=5000,
        )
        assert m.provenance.pipeline_steps == ["judge", "timeline", "scene"]
        assert m.provenance.total_latency_ms == 5000

    def test_generator_version_populated(self):
        tp = self._make_mock_timepoint()
        m = build_manifest(tp, "f", "/p", [])
        assert m.provenance.generator_version != ""
