"""Tests for app.storage.index_html module.

Covers:
    - HTML generation from manifest
    - Content correctness
    - Image section presence
"""

import pytest

from app.storage.index_html import generate_index_html, _format_bytes
from app.storage.manifest import (
    BlobManifest,
    FileEntry,
    ProvenanceInfo,
    TemporalInfo,
)


def _make_manifest(**overrides):
    defaults = dict(
        timepoint_id="tp-test",
        slug="test-slug",
        query="Tesla's Hotel 1943",
        folder_name="teslas-hotel-1943_20260209_abc123",
        full_path="/tmp/test",
        temporal=TemporalInfo(year=1943, era="WWII", location="New York"),
        provenance=ProvenanceInfo(
            text_model="gemini-2.5-flash",
            image_model="gemini-2.5-flash-image",
            generator_version="2.3.3",
            generated_at="2026-02-09T14:00:00Z",
        ),
        files=[
            FileEntry(filename="image.png", mime_type="image/png", size_bytes=50000),
            FileEntry(filename="metadata.json", mime_type="application/json", size_bytes=200),
        ],
        total_size_bytes=50200,
    )
    defaults.update(overrides)
    return BlobManifest(**defaults)


class TestFormatBytes:
    """Tests for _format_bytes helper."""

    def test_bytes(self):
        assert _format_bytes(500) == "500 B"

    def test_kilobytes(self):
        result = _format_bytes(2048)
        assert "KB" in result

    def test_megabytes(self):
        result = _format_bytes(5 * 1024 * 1024)
        assert "MB" in result

    def test_zero(self):
        assert _format_bytes(0) == "0 B"


class TestGenerateIndexHtml:
    """Tests for generate_index_html()."""

    def test_returns_html(self):
        m = _make_manifest()
        html = generate_index_html(m)
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html

    def test_contains_title(self):
        m = _make_manifest()
        html = generate_index_html(m)
        assert m.folder_name in html

    def test_contains_query(self):
        m = _make_manifest()
        html = generate_index_html(m)
        assert "Tesla" in html

    def test_contains_year(self):
        m = _make_manifest()
        html = generate_index_html(m)
        assert "1943" in html

    def test_contains_image_section(self):
        m = _make_manifest()
        html = generate_index_html(m)
        assert 'src="image.png"' in html

    def test_no_image_section_without_image(self):
        m = _make_manifest(files=[
            FileEntry(filename="metadata.json", mime_type="application/json", size_bytes=100),
        ])
        html = generate_index_html(m)
        assert '<img src=' not in html

    def test_contains_provenance(self):
        m = _make_manifest()
        html = generate_index_html(m)
        assert "gemini-2.5-flash" in html
        assert "2.3.3" in html

    def test_contains_file_list(self):
        m = _make_manifest()
        html = generate_index_html(m)
        assert "image.png" in html
        assert "metadata.json" in html

    def test_contains_stubs(self):
        m = _make_manifest()
        html = generate_index_html(m)
        assert "coming soon" in html

    def test_manifest_link(self):
        m = _make_manifest()
        html = generate_index_html(m)
        assert 'href="manifest.json"' in html
