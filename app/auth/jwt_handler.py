"""JWT access/refresh token management.

Access tokens: HS256, short-lived (15 min default).
Refresh tokens: opaque random strings, stored as SHA-256 hashes in DB.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models_auth import RefreshToken

logger = logging.getLogger(__name__)


def create_access_token(user_id: str) -> str:
    """Create a short-lived HS256 access token.

    Args:
        user_id: The user's UUID.

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> str:
    """Decode and validate an access token.

    Args:
        token: The encoded JWT.

    Returns:
        user_id (sub claim).

    Raises:
        ValueError: If token is invalid or expired.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=["HS256"]
        )
    except jwt.ExpiredSignatureError as e:
        raise ValueError("Access token has expired") from e
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid access token: {e}") from e

    if payload.get("type") != "access":
        raise ValueError("Token is not an access token")

    sub = payload.get("sub")
    if not sub:
        raise ValueError("Token missing subject")
    return sub


def _hash_token(token: str) -> str:
    """SHA-256 hash a token string."""
    return hashlib.sha256(token.encode()).hexdigest()


async def create_refresh_token(
    session: AsyncSession, user_id: str
) -> tuple[str, str]:
    """Create a new refresh token and store its hash in the database.

    Args:
        session: Database session (caller must commit).
        user_id: The user's UUID.

    Returns:
        (raw_token, token_hash) — raw_token is sent to the client,
        token_hash is stored in DB.
    """
    settings = get_settings()
    raw_token = secrets.token_urlsafe(48)
    token_hash = _hash_token(raw_token)

    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_EXPIRE_DAYS
    )

    rt = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(rt)

    return raw_token, token_hash


async def rotate_refresh_token(
    session: AsyncSession, raw_old_token: str
) -> tuple[str, str]:
    """Revoke the old refresh token and issue a new one.

    Args:
        session: Database session (caller must commit).
        raw_old_token: The raw refresh token string from the client.

    Returns:
        (new_raw_token, new_hash).

    Raises:
        ValueError: If old token is invalid, expired, or already revoked.
    """
    old_hash = _hash_token(raw_old_token)

    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == old_hash)
    )
    old_rt = result.scalar_one_or_none()

    if old_rt is None:
        raise ValueError("Refresh token not found")

    if old_rt.is_revoked:
        # Possible token reuse — revoke all tokens for this user as a safety measure
        logger.warning(
            f"Reuse of revoked refresh token detected for user {old_rt.user_id}"
        )
        all_tokens = await session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == old_rt.user_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        for t in all_tokens.scalars():
            t.revoked_at = datetime.now(timezone.utc)
        raise ValueError("Refresh token has been revoked (possible token reuse)")

    now = datetime.now(timezone.utc)
    # Handle timezone-naive datetimes from SQLite
    expires_at = old_rt.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        old_rt.revoked_at = now
        raise ValueError("Refresh token has expired")

    # Revoke old
    old_rt.revoked_at = now

    # Issue new
    new_raw, new_hash = await create_refresh_token(session, old_rt.user_id)
    return new_raw, new_hash
