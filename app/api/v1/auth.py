"""Auth API endpoints — Apple Sign-In, Google Sign-In, token refresh, user profile, logout, account deletion.

Endpoints:
    POST   /api/v1/auth/apple   — Verify Apple token, find-or-create user, return JWTs
    POST   /api/v1/auth/google  — Verify Google ID token, find-or-create user, return JWTs
    POST   /api/v1/auth/service-token — Mint JWT for user (requires X-Service-Key)
    POST   /api/v1/auth/demo    — Demo sign-in for App Store review (no auth)
    POST   /api/v1/auth/refresh  — Rotate refresh token, return new JWT pair
    GET    /api/v1/auth/me       — Return current user profile
    POST   /api/v1/auth/logout   — Revoke a refresh token
    DELETE /api/v1/auth/account  — Soft-delete user account (App Store requirement)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.apple import verify_apple_identity_token
from app.auth.credits import grant_credits
from app.auth.dependencies import get_current_user, require_admin_key, require_service_key
from app.auth.google import verify_google_id_token
from app.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    rotate_refresh_token,
)
from app.auth.schemas import (
    AppleSignInRequest,
    DevTokenRequest,
    GoogleSignInRequest,
    LogoutRequest,
    RefreshRequest,
    ServiceTokenRequest,
    TokenResponse,
    UserResponse,
)
from app.config import get_settings
from app.database import get_db_session
from app.models_auth import CreditAccount, RefreshToken, TransactionType, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory sliding-window rate limit for the demo endpoint (10 req/min per IP).
_demo_request_log: dict[str, list[float]] = defaultdict(list)


@router.post("/apple", response_model=TokenResponse)
async def apple_sign_in(
    request: AppleSignInRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Verify Apple identity token and return JWT pair.

    On first sign-in, creates a new user and grants signup credits.
    """
    try:
        claims = verify_apple_identity_token(request.identity_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e

    # Find or create user
    result = await session.execute(select(User).where(User.apple_sub == claims.sub))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            apple_sub=claims.sub,
            email=claims.email if claims.email_verified else None,
            last_login_at=datetime.now(timezone.utc),
        )
        session.add(user)
        await session.flush()  # get user.id

        # Create credit account
        account = CreditAccount(user_id=user.id, balance=0, lifetime_earned=0, lifetime_spent=0)
        session.add(account)
        await session.flush()

        # Grant signup bonus
        settings = get_settings()
        await grant_credits(
            session,
            user.id,
            settings.SIGNUP_CREDITS,
            TransactionType.SIGNUP_BONUS,
            description="Welcome bonus",
        )
    else:
        # Update last login and email if newly verified
        user.last_login_at = datetime.now(timezone.utc)
        if claims.email and claims.email_verified and not user.email:
            user.email = claims.email

    # Issue tokens
    access_token = create_access_token(user.id)
    raw_refresh, _ = await create_refresh_token(session, user.id)

    await session.commit()

    settings = get_settings()
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.JWT_ACCESS_EXPIRE_MINUTES * 60,
    )


@router.post("/google", response_model=TokenResponse)
async def google_sign_in(
    request: GoogleSignInRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Verify Google ID token and return JWT pair.

    On first sign-in, creates a new user and grants signup credits.
    """
    try:
        claims = verify_google_id_token(request.id_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e

    google_external_id = f"google:{claims.sub}"

    # Find existing user by external_id
    result = await session.execute(select(User).where(User.external_id == google_external_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            apple_sub=google_external_id,  # satisfies NOT NULL constraint
            external_id=google_external_id,
            email=claims.email if claims.email_verified else None,
            display_name=claims.name,
            last_login_at=datetime.now(timezone.utc),
        )
        session.add(user)
        await session.flush()  # get user.id

        # Create credit account
        account = CreditAccount(user_id=user.id, balance=0, lifetime_earned=0, lifetime_spent=0)
        session.add(account)
        await session.flush()

        # Grant signup bonus
        settings = get_settings()
        await grant_credits(
            session,
            user.id,
            settings.SIGNUP_CREDITS,
            TransactionType.SIGNUP_BONUS,
            description="Welcome bonus",
        )
    else:
        # Update last login and email if newly verified
        user.last_login_at = datetime.now(timezone.utc)
        if claims.email and claims.email_verified and not user.email:
            user.email = claims.email
        if claims.name and not user.display_name:
            user.display_name = claims.name

    # Issue tokens
    access_token = create_access_token(user.id)
    raw_refresh, _ = await create_refresh_token(session, user.id)

    await session.commit()

    settings = get_settings()
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.JWT_ACCESS_EXPIRE_MINUTES * 60,
    )


@router.post("/dev/token", response_model=TokenResponse)
async def dev_token(
    request: DevTokenRequest,
    session: AsyncSession = Depends(get_db_session),
    _admin: None = Depends(require_admin_key),
) -> TokenResponse:
    """Create a test user (or find existing by email) and return a JWT pair.

    Requires X-Admin-Key header. Grants signup credits on first creation.
    """
    import hashlib

    # Deterministic apple_sub from email so find-or-create is stable
    email_hash = hashlib.sha256(request.email.encode()).hexdigest()[:16]
    synthetic_sub = f"dev_{email_hash}"

    result = await session.execute(select(User).where(User.apple_sub == synthetic_sub))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            apple_sub=synthetic_sub,
            email=request.email,
            display_name=request.display_name,
            last_login_at=datetime.now(timezone.utc),
        )
        session.add(user)
        await session.flush()

        # Create credit account
        account = CreditAccount(user_id=user.id, balance=0, lifetime_earned=0, lifetime_spent=0)
        session.add(account)
        await session.flush()

        # Grant signup bonus
        settings = get_settings()
        await grant_credits(
            session,
            user.id,
            settings.SIGNUP_CREDITS,
            TransactionType.SIGNUP_BONUS,
            description="Welcome bonus (dev)",
        )
        logger.info("Dev user created: %s (%s)", user.id, request.email)
    else:
        user.last_login_at = datetime.now(timezone.utc)
        if request.display_name:
            user.display_name = request.display_name

    # Issue tokens
    access_token = create_access_token(user.id)
    raw_refresh, _ = await create_refresh_token(session, user.id)

    await session.commit()

    settings = get_settings()
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.JWT_ACCESS_EXPIRE_MINUTES * 60,
    )


@router.post("/service-token", response_model=TokenResponse)
async def service_token(
    request: ServiceTokenRequest,
    _key: None = Depends(require_service_key),
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Mint a JWT pair for an existing user, on behalf of a trusted service.

    Called by billing / Pro Cloud after they have already authenticated the
    user through their own auth flow.  Requires a valid X-Service-Key header.
    """
    # Verify the user exists and is active
    result = await session.execute(select(User).where(User.id == request.user_id))
    user = result.scalar_one_or_none()

    if user is None:
        # Also try external_id for Pro Cloud users
        result = await session.execute(select(User).where(User.external_id == request.user_id))
        user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {request.user_id} not found or inactive",
        )

    # Issue tokens
    access_token = create_access_token(user.id)
    raw_refresh, _ = await create_refresh_token(session, user.id)

    await session.commit()

    settings = get_settings()
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.JWT_ACCESS_EXPIRE_MINUTES * 60,
    )


@router.post("/demo", response_model=TokenResponse)
async def demo_sign_in(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Public demo sign-in for App Store reviewers and simulator testing.

    No authentication required. Returns a JWT pair for a fixed demo account.
    Rate-limited to 10 requests per minute per IP.
    """
    import hashlib
    import time

    # --- inline rate limit (10 req/min sliding window) ---
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = 60.0
    max_requests = 10

    log = _demo_request_log[client_ip]
    # Prune entries older than the window
    _demo_request_log[client_ip] = log = [t for t in log if now - t < window]

    if len(log) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demo sign-in rate limit exceeded. Try again in 60 seconds.",
            headers={"Retry-After": "60"},
        )
    log.append(now)

    # --- find or create demo user ---
    demo_email = "demo@timepointai.com"
    demo_display_name = "Demo User"
    email_hash = hashlib.sha256(demo_email.encode()).hexdigest()[:16]
    synthetic_sub = f"demo_{email_hash}"

    result = await session.execute(select(User).where(User.apple_sub == synthetic_sub))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            apple_sub=synthetic_sub,
            email=demo_email,
            display_name=demo_display_name,
            last_login_at=datetime.now(timezone.utc),
        )
        session.add(user)
        await session.flush()

        account = CreditAccount(user_id=user.id, balance=0, lifetime_earned=0, lifetime_spent=0)
        session.add(account)
        await session.flush()

        settings = get_settings()
        await grant_credits(
            session,
            user.id,
            settings.SIGNUP_CREDITS,
            TransactionType.SIGNUP_BONUS,
            description="Welcome bonus (demo)",
        )
        logger.info("Demo user created: %s", user.id)
    else:
        user.last_login_at = datetime.now(timezone.utc)

    # Issue tokens
    access_token = create_access_token(user.id)
    raw_refresh, _ = await create_refresh_token(session, user.id)

    await session.commit()

    settings = get_settings()
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.JWT_ACCESS_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    request: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Rotate refresh token and return a new JWT pair."""
    try:
        new_raw, new_hash = await rotate_refresh_token(session, request.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e

    # Retrieve user_id from the new token record
    from app.models_auth import RefreshToken

    result = await session.execute(select(RefreshToken).where(RefreshToken.token_hash == new_hash))
    new_rt = result.scalar_one()

    access_token = create_access_token(new_rt.user_id)
    await session.commit()

    settings = get_settings()
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_raw,
        expires_in=settings.JWT_ACCESS_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User | None = Depends(get_current_user),
) -> UserResponse:
    """Return the current user's profile.

    Requires authentication when AUTH_ENABLED=true.
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return UserResponse.model_validate(user)


@router.post("/logout", status_code=200)
async def logout(
    request: LogoutRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Revoke a refresh token (logout).

    Finds the hashed token and sets revoked_at. Returns 200 regardless
    of whether the token was found (to avoid token-existence oracle).
    """
    import hashlib

    token_hash = hashlib.sha256(request.refresh_token.encode()).hexdigest()

    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    rt = result.scalar_one_or_none()

    if rt is not None:
        rt.revoked_at = datetime.now(timezone.utc)
        await session.commit()

    return {"detail": "Logged out"}


@router.delete("/account", status_code=200)
async def delete_account(
    user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Soft-delete user account (App Store requirement).

    Sets user.is_active = False and revokes all refresh tokens.
    Does NOT hard-delete data to preserve ledger integrity.
    Requires Bearer JWT.
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    # Deactivate user
    user.is_active = False

    # Revoke all active refresh tokens
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    now = datetime.now(timezone.utc)
    for rt in result.scalars():
        rt.revoked_at = now

    await session.commit()

    return {"detail": "Account deactivated"}
