"""Apple Sign-In token verification.

Fetches Apple's JWKS and verifies identity tokens (RS256).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import jwt
from jwt import PyJWKClient

from app.config import get_settings

logger = logging.getLogger(__name__)

APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"

# Module-level cache for the JWKS client (keys auto-cached by PyJWKClient)
_jwks_client: PyJWKClient | None = None
_jwks_client_created_at: float = 0.0
_JWKS_CACHE_TTL = 86400  # 24 hours


def _get_jwks_client() -> PyJWKClient:
    """Get or create a cached JWKS client."""
    global _jwks_client, _jwks_client_created_at

    now = time.time()
    if _jwks_client is None or (now - _jwks_client_created_at) > _JWKS_CACHE_TTL:
        _jwks_client = PyJWKClient(APPLE_JWKS_URL, cache_keys=True)
        _jwks_client_created_at = now

    return _jwks_client


@dataclass
class AppleTokenClaims:
    """Parsed claims from a verified Apple identity token."""

    sub: str
    email: str | None
    email_verified: bool


def verify_apple_identity_token(identity_token: str) -> AppleTokenClaims:
    """Verify an Apple identity token and extract claims.

    Args:
        identity_token: The JWT identity token from Apple Sign-In on iOS.

    Returns:
        AppleTokenClaims with sub, email, email_verified.

    Raises:
        ValueError: If the token is invalid, expired, or audience mismatch.
    """
    settings = get_settings()
    bundle_id = settings.APPLE_BUNDLE_ID

    if not bundle_id:
        raise ValueError("APPLE_BUNDLE_ID not configured")

    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(identity_token)

        payload: dict[str, Any] = jwt.decode(
            identity_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=bundle_id,
            issuer=APPLE_ISSUER,
        )
    except jwt.ExpiredSignatureError as e:
        raise ValueError("Apple identity token has expired") from e
    except jwt.InvalidAudienceError as e:
        raise ValueError("Apple identity token audience mismatch") from e
    except jwt.InvalidIssuerError as e:
        raise ValueError("Apple identity token issuer mismatch") from e
    except Exception as e:
        logger.error(f"Apple token verification failed: {e}")
        raise ValueError(f"Invalid Apple identity token: {e}") from e

    return AppleTokenClaims(
        sub=payload["sub"],
        email=payload.get("email"),
        email_verified=payload.get("email_verified", False),
    )
