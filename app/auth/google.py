"""Google Sign-In ID token verification.

Fetches Google's JWKS and verifies ID tokens (RS256).
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

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

# Module-level cache for the JWKS client (keys auto-cached by PyJWKClient)
_jwks_client: PyJWKClient | None = None
_jwks_client_created_at: float = 0.0
_JWKS_CACHE_TTL = 86400  # 24 hours


def _get_jwks_client() -> PyJWKClient:
    """Get or create a cached JWKS client."""
    global _jwks_client, _jwks_client_created_at

    now = time.time()
    if _jwks_client is None or (now - _jwks_client_created_at) > _JWKS_CACHE_TTL:
        _jwks_client = PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True)
        _jwks_client_created_at = now

    return _jwks_client


@dataclass
class GoogleTokenClaims:
    """Parsed claims from a verified Google ID token."""

    sub: str
    email: str | None
    email_verified: bool
    name: str | None
    picture: str | None


def verify_google_id_token(id_token: str) -> GoogleTokenClaims:
    """Verify a Google ID token and extract claims.

    Args:
        id_token: The JWT ID token from Google Sign-In.

    Returns:
        GoogleTokenClaims with sub, email, email_verified, name, picture.

    Raises:
        ValueError: If the token is invalid, expired, or audience mismatch.
    """
    settings = get_settings()
    client_id = settings.GOOGLE_OAUTH_CLIENT_ID

    if not client_id:
        raise ValueError("GOOGLE_OAUTH_CLIENT_ID not configured")

    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(id_token)

        payload: dict[str, Any] = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=GOOGLE_ISSUERS,
        )
    except jwt.ExpiredSignatureError as e:
        raise ValueError("Google ID token has expired") from e
    except jwt.InvalidAudienceError as e:
        raise ValueError("Google ID token audience mismatch") from e
    except jwt.InvalidIssuerError as e:
        raise ValueError("Google ID token issuer mismatch") from e
    except Exception as e:
        logger.error(f"Google token verification failed: {e}")
        raise ValueError(f"Invalid Google ID token: {e}") from e

    return GoogleTokenClaims(
        sub=payload["sub"],
        email=payload.get("email"),
        email_verified=payload.get("email_verified", False),
        name=payload.get("name"),
        picture=payload.get("picture"),
    )
