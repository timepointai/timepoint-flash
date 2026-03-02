"""Tests for the TDF (Timepoint Data Format) export endpoint.

Verifies that:
  - The endpoint returns a valid TDF record for a completed timepoint
  - The tdf_hash is a stable SHA-256 of the canonicalised payload
  - 404 is returned for non-existent timepoints
  - The record structure matches the TDFRecord schema from timepoint-tdf
"""

import hashlib
import json

import pytest

from app.api.v1.tdf import _compute_tdf_hash


@pytest.mark.fast
class TestComputeTdfHash:
    """Unit tests for the _compute_tdf_hash helper."""

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


@pytest.mark.fast
class TestTdfEndpoint:
    """Integration-style tests for GET /api/v1/timepoints/{id}/tdf."""

    @pytest.mark.asyncio
    async def test_tdf_export_completed_timepoint(self, test_client, sample_timepoint):
        """A completed timepoint should return a well-formed TDF record."""
        resp = await test_client.get(f"/api/v1/timepoints/{sample_timepoint.id}/tdf")
        assert resp.status_code == 200
        data = resp.json()

        assert data["id"] == sample_timepoint.id
        assert data["version"] == "1.0.0"
        assert data["source"] == "flash"
        assert data["timestamp"] is not None
        assert data["provenance"]["generator"] == "timepoint-flash"
        assert data["provenance"]["flash_id"] == sample_timepoint.id
        assert isinstance(data["payload"], dict)
        assert len(data["tdf_hash"]) == 64

    @pytest.mark.asyncio
    async def test_tdf_payload_contains_expected_keys(self, test_client, sample_timepoint):
        resp = await test_client.get(f"/api/v1/timepoints/{sample_timepoint.id}/tdf")
        payload = resp.json()["payload"]
        expected_keys = {
            "query",
            "slug",
            "year",
            "month",
            "day",
            "season",
            "time_of_day",
            "era",
            "location",
            "scene_data",
            "character_data",
            "dialog",
            "grounding_data",
            "moment_data",
            "metadata",
        }
        assert expected_keys == set(payload.keys())

    @pytest.mark.asyncio
    async def test_tdf_hash_matches_payload(self, test_client, sample_timepoint):
        """The tdf_hash must be the SHA-256 of the canonicalised payload."""
        resp = await test_client.get(f"/api/v1/timepoints/{sample_timepoint.id}/tdf")
        data = resp.json()
        assert data["tdf_hash"] == _compute_tdf_hash(data["payload"])

    @pytest.mark.asyncio
    async def test_tdf_404_for_missing_timepoint(self, test_client, test_db):
        resp = await test_client.get("/api/v1/timepoints/nonexistent-id-000/tdf")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_tdf_hash_stable_across_requests(self, test_client, sample_timepoint):
        """Two requests for the same timepoint must produce the same hash."""
        r1 = await test_client.get(f"/api/v1/timepoints/{sample_timepoint.id}/tdf")
        r2 = await test_client.get(f"/api/v1/timepoints/{sample_timepoint.id}/tdf")
        assert r1.json()["tdf_hash"] == r2.json()["tdf_hash"]
