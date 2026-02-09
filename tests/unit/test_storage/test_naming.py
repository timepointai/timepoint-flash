"""Tests for app.storage.naming module.

Covers:
    - sanitize_slug: basic sanitization, edge cases, unicode, max length
    - generate_folder_name: format, deterministic output
    - generate_folder_path: path structure
"""

import re
from datetime import datetime, timezone

import pytest

from app.storage.naming import generate_folder_name, generate_folder_path, sanitize_slug


class TestSanitizeSlug:
    """Tests for sanitize_slug()."""

    def test_basic_query(self):
        slug = sanitize_slug("Tesla's New Yorker Hotel, 1943!")
        assert slug == "teslas-new-yorker-hotel-1943"

    def test_lowercase(self):
        slug = sanitize_slug("UPPER CASE QUERY")
        assert slug == "upper-case-query"

    def test_strips_special_chars(self):
        slug = sanitize_slug("hello@world#2024!")
        assert slug == "helloworld2024"

    def test_collapses_hyphens(self):
        slug = sanitize_slug("too---many---hyphens")
        assert slug == "too-many-hyphens"

    def test_strips_leading_trailing_hyphens(self):
        slug = sanitize_slug("---leading-trailing---")
        assert slug == "leading-trailing"

    def test_spaces_to_hyphens(self):
        slug = sanitize_slug("signing of the declaration")
        assert slug == "signing-of-the-declaration"

    def test_underscores_to_hyphens(self):
        slug = sanitize_slug("hello_world_test")
        assert slug == "hello-world-test"

    def test_max_length_default(self):
        long_query = "a" * 100
        slug = sanitize_slug(long_query)
        assert len(slug) <= 60

    def test_max_length_custom(self):
        slug = sanitize_slug("abcdefghijklmnop", max_length=10)
        assert len(slug) <= 10

    def test_empty_string_fallback(self):
        slug = sanitize_slug("!@#$%^&*()")
        assert slug.startswith("timepoint-")
        assert len(slug) == len("timepoint-") + 6

    def test_whitespace_only_fallback(self):
        slug = sanitize_slug("   ")
        assert slug.startswith("timepoint-")

    def test_unicode_stripped(self):
        slug = sanitize_slug("caf\u00e9 au lait")
        # Non-ascii chars stripped, result is "caf-au-lait"
        assert "caf" in slug
        assert "au" in slug

    def test_only_valid_chars(self):
        slug = sanitize_slug("Any Query! @ 2024")
        assert re.match(r"^[a-z0-9-]+$", slug)

    def test_truncation_doesnt_leave_trailing_hyphen(self):
        # Make a query where truncation at 10 would end with hyphen
        slug = sanitize_slug("abcdefghi-jklmnop", max_length=10)
        assert not slug.endswith("-")


class TestGenerateFolderName:
    """Tests for generate_folder_name()."""

    def test_format(self):
        date = datetime(2026, 2, 9, tzinfo=timezone.utc)
        name = generate_folder_name("Tesla's Hotel", date=date, uuid_str="a3f2b1")
        assert name == "teslas-hotel_20260209_a3f2b1"

    def test_contains_date(self):
        date = datetime(2025, 12, 25, tzinfo=timezone.utc)
        name = generate_folder_name("christmas", date=date, uuid_str="abc123")
        assert "20251225" in name

    def test_uuid_truncated(self):
        name = generate_folder_name("test", uuid_str="abcdefghijklmnop")
        assert name.endswith("_abcdef")

    def test_auto_uuid(self):
        name = generate_folder_name("test")
        parts = name.split("_")
        assert len(parts) == 3
        assert len(parts[2]) == 6

    def test_deterministic_with_fixed_inputs(self):
        date = datetime(2026, 1, 1, tzinfo=timezone.utc)
        n1 = generate_folder_name("q", date=date, uuid_str="111111")
        n2 = generate_folder_name("q", date=date, uuid_str="111111")
        assert n1 == n2


class TestGenerateFolderPath:
    """Tests for generate_folder_path()."""

    def test_path_structure(self):
        date = datetime(2026, 2, 9, tzinfo=timezone.utc)
        path, name = generate_folder_path(
            root="/output/timepoints",
            query="test query",
            date=date,
            uuid_str="abc123",
        )
        assert path == "/output/timepoints/2026/02/test-query_20260209_abc123"
        assert name == "test-query_20260209_abc123"

    def test_year_month_extraction(self):
        date = datetime(2025, 11, 15, tzinfo=timezone.utc)
        path, _ = generate_folder_path(
            root="./out", query="x", date=date, uuid_str="000000",
        )
        assert "/2025/11/" in path

    def test_returns_tuple(self):
        result = generate_folder_path(root="./out", query="test")
        assert isinstance(result, tuple)
        assert len(result) == 2
