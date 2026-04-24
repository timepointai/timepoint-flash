"""Unit tests for app.auth.gateway_signing (API-4).

These tests exercise the pure HMAC verification helpers. Integration tests for
the edge middleware live in tests/integration/test_gateway_auth_middleware.py.
"""

from __future__ import annotations

import time

import pytest

from app.auth.gateway_signing import (
    MAX_CLOCK_SKEW_SECONDS,
    SIGNATURE_VERSION,
    build_canonical_string,
    compute_signature,
    parse_signature_header,
    verify_gateway_signature,
)


def _valid_sig(secret: str, method: str, path: str, user_id: str, ts: int) -> str:
    canonical = build_canonical_string(method, path, user_id, str(ts))
    return f"{SIGNATURE_VERSION}=" + compute_signature(secret, canonical)


def test_build_canonical_string_is_stable() -> None:
    canonical = build_canonical_string("post", "/api/v1/generate", "u-1", "1700000000")
    assert canonical == "v1\nPOST\n/api/v1/generate\nu-1\n1700000000"


def test_parse_signature_header_accepts_v1_prefix() -> None:
    assert parse_signature_header("v1=abc123") == "abc123"
    assert parse_signature_header("v2=abc123") is None
    assert parse_signature_header("") is None
    assert parse_signature_header("v1=") is None


def test_verify_gateway_signature_happy_path() -> None:
    secret = "test-secret"
    now = int(time.time())
    sig = _valid_sig(secret, "POST", "/api/v1/generate", "u-1", now)

    assert verify_gateway_signature(
        secret=secret,
        method="POST",
        path="/api/v1/generate",
        user_id="u-1",
        timestamp_header=str(now),
        signature_header=sig,
        now=now,
    )


def test_verify_gateway_signature_rejects_wrong_secret() -> None:
    secret = "test-secret"
    now = int(time.time())
    sig = _valid_sig(secret, "POST", "/api/v1/generate", "u-1", now)

    assert not verify_gateway_signature(
        secret="different-secret",
        method="POST",
        path="/api/v1/generate",
        user_id="u-1",
        timestamp_header=str(now),
        signature_header=sig,
        now=now,
    )


def test_verify_gateway_signature_rejects_tampered_user_id() -> None:
    """The signature binds user_id — changing it must invalidate the request."""
    secret = "test-secret"
    now = int(time.time())
    # Gateway signed for user u-1 …
    sig = _valid_sig(secret, "POST", "/api/v1/generate", "u-1", now)

    # … but attacker swaps header to u-2.
    assert not verify_gateway_signature(
        secret=secret,
        method="POST",
        path="/api/v1/generate",
        user_id="u-2",
        timestamp_header=str(now),
        signature_header=sig,
        now=now,
    )


def test_verify_gateway_signature_rejects_tampered_path() -> None:
    secret = "test-secret"
    now = int(time.time())
    sig = _valid_sig(secret, "POST", "/api/v1/generate", "u-1", now)

    assert not verify_gateway_signature(
        secret=secret,
        method="POST",
        path="/api/v1/admin/wipe",
        user_id="u-1",
        timestamp_header=str(now),
        signature_header=sig,
        now=now,
    )


def test_verify_gateway_signature_rejects_tampered_method() -> None:
    secret = "test-secret"
    now = int(time.time())
    sig = _valid_sig(secret, "POST", "/api/v1/generate", "u-1", now)

    assert not verify_gateway_signature(
        secret=secret,
        method="DELETE",
        path="/api/v1/generate",
        user_id="u-1",
        timestamp_header=str(now),
        signature_header=sig,
        now=now,
    )


def test_verify_gateway_signature_rejects_stale_timestamp() -> None:
    secret = "test-secret"
    signed_at = 1_700_000_000
    sig = _valid_sig(secret, "POST", "/api/v1/generate", "u-1", signed_at)

    # Verify at a time beyond the skew window.
    assert not verify_gateway_signature(
        secret=secret,
        method="POST",
        path="/api/v1/generate",
        user_id="u-1",
        timestamp_header=str(signed_at),
        signature_header=sig,
        now=signed_at + MAX_CLOCK_SKEW_SECONDS + 1,
    )


def test_verify_gateway_signature_rejects_future_timestamp() -> None:
    secret = "test-secret"
    signed_at = 1_700_000_000
    sig = _valid_sig(secret, "POST", "/api/v1/generate", "u-1", signed_at)

    # Timestamp is way in the future (clock-skew replay attempt).
    assert not verify_gateway_signature(
        secret=secret,
        method="POST",
        path="/api/v1/generate",
        user_id="u-1",
        timestamp_header=str(signed_at),
        signature_header=sig,
        now=signed_at - MAX_CLOCK_SKEW_SECONDS - 1,
    )


def test_verify_gateway_signature_rejects_nonnumeric_timestamp() -> None:
    secret = "test-secret"
    now = int(time.time())
    sig = _valid_sig(secret, "POST", "/api/v1/generate", "u-1", now)

    assert not verify_gateway_signature(
        secret=secret,
        method="POST",
        path="/api/v1/generate",
        user_id="u-1",
        timestamp_header="not-a-number",
        signature_header=sig,
        now=now,
    )


def test_verify_gateway_signature_rejects_missing_headers() -> None:
    now = int(time.time())
    # Empty signature header
    assert not verify_gateway_signature(
        secret="test-secret",
        method="POST",
        path="/api/v1/generate",
        user_id="u-1",
        timestamp_header=str(now),
        signature_header="",
        now=now,
    )
    # Empty timestamp header
    assert not verify_gateway_signature(
        secret="test-secret",
        method="POST",
        path="/api/v1/generate",
        user_id="u-1",
        timestamp_header="",
        signature_header="v1=abc",
        now=now,
    )


def test_verify_gateway_signature_rejects_empty_secret() -> None:
    """A missing secret must never validate — fail-closed."""
    now = int(time.time())
    sig = _valid_sig("any-secret", "POST", "/api/v1/generate", "u-1", now)

    assert not verify_gateway_signature(
        secret="",
        method="POST",
        path="/api/v1/generate",
        user_id="u-1",
        timestamp_header=str(now),
        signature_header=sig,
        now=now,
    )


def test_verify_gateway_signature_rejects_wrong_version_prefix() -> None:
    secret = "test-secret"
    now = int(time.time())
    canonical = build_canonical_string("POST", "/api/v1/generate", "u-1", str(now))
    digest = compute_signature(secret, canonical)

    # Bare hex without "v1=" prefix is not accepted.
    assert not verify_gateway_signature(
        secret=secret,
        method="POST",
        path="/api/v1/generate",
        user_id="u-1",
        timestamp_header=str(now),
        signature_header=digest,
        now=now,
    )


@pytest.mark.parametrize("user_id", ["", "u-1", "user:with:colons", "u-åéîøü"])
def test_verify_gateway_signature_handles_diverse_user_ids(user_id: str) -> None:
    secret = "test-secret"
    now = int(time.time())
    sig = _valid_sig(secret, "GET", "/api/v1/users/me", user_id, now)

    assert verify_gateway_signature(
        secret=secret,
        method="GET",
        path="/api/v1/users/me",
        user_id=user_id,
        timestamp_header=str(now),
        signature_header=sig,
        now=now,
    )
