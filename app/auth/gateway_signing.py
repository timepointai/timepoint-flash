"""HMAC verification for signed requests from the API Gateway.

The Gateway sends outbound requests to Flash with:

* ``X-Gateway-Timestamp`` — unix epoch seconds (string)
* ``X-Gateway-Signature`` — ``v1=<hex>`` HMAC-SHA256 over the canonical string

Canonical signing input::

    v1\\n{METHOD}\\n{PATH}\\n{X-User-Id}\\n{timestamp}

The shared secret is ``GATEWAY_SIGNING_SECRET``. Requests whose signature
verifies are trusted to carry a gateway-authenticated ``X-User-Id``; everything
else is either rejected (``REQUIRE_SIGNED_GATEWAY=True``) or treated as an
unauthenticated system call (``ALLOW_LEGACY_SERVICE_KEY=True``), which may not
claim a user identity.

Tests:
    - tests/unit/test_gateway_signing.py
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "X-Gateway-Signature"
TIMESTAMP_HEADER = "X-Gateway-Timestamp"
SIGNATURE_VERSION = "v1"
MAX_CLOCK_SKEW_SECONDS = 300


def build_canonical_string(
    method: str,
    path: str,
    user_id: str,
    timestamp: str,
) -> str:
    """Build the canonical signing string.

    Args:
        method: HTTP method (will be upper-cased).
        path: Request path (e.g. ``/api/v1/timepoints/generate``).
        user_id: X-User-Id header value or empty string for system calls.
        timestamp: Unix epoch seconds as a string.

    Returns:
        The newline-joined canonical string.
    """
    return "\n".join(
        [
            SIGNATURE_VERSION,
            method.upper(),
            path,
            user_id or "",
            timestamp,
        ]
    )


def compute_signature(secret: str, canonical: str) -> str:
    """Compute the HMAC-SHA256 hex digest."""
    return hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def parse_signature_header(value: str) -> str | None:
    """Parse ``v1=<hex>`` and return the hex digest, or None if invalid."""
    if not value:
        return None
    prefix = f"{SIGNATURE_VERSION}="
    if not value.startswith(prefix):
        return None
    return value[len(prefix) :] or None


def verify_gateway_signature(
    *,
    secret: str,
    method: str,
    path: str,
    user_id: str,
    timestamp_header: str,
    signature_header: str,
    now: int | None = None,
    max_skew_seconds: int = MAX_CLOCK_SKEW_SECONDS,
) -> bool:
    """Verify a Gateway HMAC signature.

    Args:
        secret: The shared signing secret (GATEWAY_SIGNING_SECRET).
        method: Request HTTP method.
        path: Request path.
        user_id: X-User-Id header value (empty string if absent).
        timestamp_header: Raw X-Gateway-Timestamp header value.
        signature_header: Raw X-Gateway-Signature header value.
        now: Override for current unix time (for tests).
        max_skew_seconds: Maximum allowed clock skew.

    Returns:
        True iff the signature is valid AND the timestamp is within the
        allowed skew window AND the secret is configured.
    """
    if not secret:
        return False
    if not timestamp_header or not signature_header:
        return False

    received = parse_signature_header(signature_header)
    if received is None:
        return False

    try:
        ts_int = int(timestamp_header)
    except ValueError:
        return False

    current = int(time.time()) if now is None else now
    if abs(current - ts_int) > max_skew_seconds:
        return False

    canonical = build_canonical_string(method, path, user_id, timestamp_header)
    expected = compute_signature(secret, canonical)

    return hmac.compare_digest(expected, received)
