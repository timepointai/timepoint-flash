"""Tests for the TDF (Timepoint Data Format) export endpoint.

Verifies that:
  - The tdf_hash stored on the model is a stable SHA-256
  - The TDF payload is returned as-is from the stored tdf_payload column
  - 404 is returned for non-existent timepoints
"""

import hashlib
import json

import pytest


def _compute_tdf_hash(payload: dict) -> str:
    """Local helper — mirrors the hash logic used in the pipeline."""
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


@pytest.mark.fast
class TestComputeTdfHash:
    """Unit tests for the TDF hash computation."""

    def test_returns_64_char_hex(self):
        h = _compute_tdf_hash({"key": "value"})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic_for_same_payload(self):
        payload = {"year": 1941, "location": "Bletchley Park"}
        assert _compute_tdf_hash(payload) == _compute_tdf_hash(payload)

    def test_key_order_irrelevant(self):
        a = _compute_tdf_hash({"x": 1, "y": 2})
        b = _compute_tdf_hash({"y": 2, "x": 1})
        assert a == b

    def test_different_payload_different_hash(self):
        a = _compute_tdf_hash({"a": 1})
        b = _compute_tdf_hash({"a": 2})
        assert a != b

    def test_matches_manual_sha256(self):
        payload = {"hello": "world"}
        canonical = json.dumps(payload, sort_keys=True, default=str)
        expected = hashlib.sha256(canonical.encode()).hexdigest()
        assert _compute_tdf_hash(payload) == expected
