"""Tests for auth module — Apple token verification, JWT handling, credit deps."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest
from sqlalchemy import select

from app.auth.apple import verify_apple_identity_token
from app.auth.credits import check_balance, grant_credits, spend_credits
from app.auth.jwt_handler import (
    _hash_token,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    rotate_refresh_token,
)
from app.models_auth import (
    CreditAccount,
    CreditTransaction,
    RefreshToken,
    TransactionType,
    User,
)

# ---------------------------------------------------------------------------
# JWT access token tests
# ---------------------------------------------------------------------------


class TestAccessToken:
    def test_create_and_decode(self):
        token = create_access_token("user-123")
        assert isinstance(token, str)
        user_id = decode_access_token(token)
        assert user_id == "user-123"

    def test_expired_token(self):
        with patch("app.auth.jwt_handler.get_settings") as mock_settings:
            s = MagicMock()
            s.JWT_SECRET_KEY = "test-secret-key-for-testing"
            s.JWT_ACCESS_EXPIRE_MINUTES = -1  # already expired
            mock_settings.return_value = s

            token = create_access_token("user-123")

            with pytest.raises(ValueError, match="expired"):
                decode_access_token(token)

    def test_invalid_token(self):
        with pytest.raises(ValueError, match="Invalid"):
            decode_access_token("not-a-jwt")

    def test_wrong_type_claim(self):
        """A refresh-style token should be rejected by decode_access_token."""
        with patch("app.auth.jwt_handler.get_settings") as mock_settings:
            s = MagicMock()
            s.JWT_SECRET_KEY = "test-secret-key-for-testing"
            s.JWT_ACCESS_EXPIRE_MINUTES = 15
            mock_settings.return_value = s

            payload = {
                "sub": "user-123",
                "iat": datetime.now(timezone.utc),
                "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
                "type": "refresh",
            }
            token = pyjwt.encode(payload, "test-secret-key-for-testing", algorithm="HS256")

            with pytest.raises(ValueError, match="not an access token"):
                decode_access_token(token)


# ---------------------------------------------------------------------------
# Refresh token tests
# ---------------------------------------------------------------------------


class TestRefreshToken:
    @pytest.mark.asyncio
    async def test_create_refresh_token(self, db_session):
        """Create a user then issue a refresh token."""
        user = User(apple_sub="test-sub-001")
        db_session.add(user)
        await db_session.flush()

        raw, token_hash = await create_refresh_token(db_session, user.id)
        await db_session.commit()

        assert isinstance(raw, str)
        assert token_hash == _hash_token(raw)

        # Verify stored in DB
        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        rt = result.scalar_one()
        assert rt.user_id == user.id
        assert rt.revoked_at is None

    @pytest.mark.asyncio
    async def test_rotate_refresh_token(self, db_session):
        """Rotate should revoke old and issue new."""
        user = User(apple_sub="test-sub-002")
        db_session.add(user)
        await db_session.flush()

        raw_old, old_hash = await create_refresh_token(db_session, user.id)
        await db_session.commit()

        new_raw, new_hash = await rotate_refresh_token(db_session, raw_old)
        await db_session.commit()

        assert new_raw != raw_old
        assert new_hash != old_hash

        # Old should be revoked
        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == old_hash)
        )
        old_rt = result.scalar_one()
        assert old_rt.revoked_at is not None

    @pytest.mark.asyncio
    async def test_reuse_revoked_token(self, db_session):
        """Using a revoked token should fail and revoke all tokens for the user."""
        user = User(apple_sub="test-sub-003")
        db_session.add(user)
        await db_session.flush()

        raw_old, _ = await create_refresh_token(db_session, user.id)
        await db_session.commit()

        # Rotate once (revokes old)
        await rotate_refresh_token(db_session, raw_old)
        await db_session.commit()

        # Attempt to reuse the old token
        with pytest.raises(ValueError, match="revoked"):
            await rotate_refresh_token(db_session, raw_old)


# ---------------------------------------------------------------------------
# Apple token verification (mocked JWKS)
# ---------------------------------------------------------------------------


class TestAppleVerification:
    def test_missing_bundle_id(self):
        with patch("app.auth.apple.get_settings") as mock_settings:
            s = MagicMock()
            s.APPLE_BUNDLE_ID = ""
            mock_settings.return_value = s

            with pytest.raises(ValueError, match="APPLE_BUNDLE_ID"):
                verify_apple_identity_token("fake.jwt.token")

    def test_invalid_token(self):
        with patch("app.auth.apple.get_settings") as mock_settings:
            s = MagicMock()
            s.APPLE_BUNDLE_ID = "com.example.app"
            mock_settings.return_value = s

            with pytest.raises(ValueError, match="Invalid"):
                verify_apple_identity_token("not-a-real-token")


# ---------------------------------------------------------------------------
# Credit operations
# ---------------------------------------------------------------------------


class TestCredits:
    @pytest.mark.asyncio
    async def test_grant_credits(self, db_session):
        user = User(apple_sub="credit-test-001")
        db_session.add(user)
        await db_session.flush()

        account = CreditAccount(user_id=user.id, balance=0, lifetime_earned=0, lifetime_spent=0)
        db_session.add(account)
        await db_session.flush()

        txn = await grant_credits(db_session, user.id, 50, TransactionType.SIGNUP_BONUS, "Welcome")
        await db_session.commit()

        assert txn.amount == 50
        assert txn.balance_after == 50
        assert account.balance == 50
        assert account.lifetime_earned == 50

    @pytest.mark.asyncio
    async def test_spend_credits(self, db_session):
        user = User(apple_sub="credit-test-002")
        db_session.add(user)
        await db_session.flush()

        account = CreditAccount(user_id=user.id, balance=50, lifetime_earned=50, lifetime_spent=0)
        db_session.add(account)
        await db_session.flush()

        txn = await spend_credits(
            db_session, user.id, 5, TransactionType.GENERATION, description="Test"
        )
        await db_session.commit()

        assert txn.amount == -5
        assert txn.balance_after == 45
        assert account.balance == 45
        assert account.lifetime_spent == 5

    @pytest.mark.asyncio
    async def test_insufficient_credits(self, db_session):
        user = User(apple_sub="credit-test-003")
        db_session.add(user)
        await db_session.flush()

        account = CreditAccount(user_id=user.id, balance=2, lifetime_earned=2, lifetime_spent=0)
        db_session.add(account)
        await db_session.flush()

        with pytest.raises(ValueError, match="Insufficient"):
            await spend_credits(db_session, user.id, 5, TransactionType.GENERATION)

    @pytest.mark.asyncio
    async def test_check_balance(self, db_session):
        user = User(apple_sub="credit-test-004")
        db_session.add(user)
        await db_session.flush()

        account = CreditAccount(user_id=user.id, balance=10, lifetime_earned=10, lifetime_spent=0)
        db_session.add(account)
        await db_session.flush()

        assert await check_balance(db_session, user.id, 10) is True
        assert await check_balance(db_session, user.id, 11) is False

    @pytest.mark.asyncio
    async def test_signup_bonus_once(self, db_session):
        """Signup bonus should only be granted on first sign-in."""
        user = User(apple_sub="credit-test-005")
        db_session.add(user)
        await db_session.flush()

        account = CreditAccount(user_id=user.id, balance=0, lifetime_earned=0, lifetime_spent=0)
        db_session.add(account)
        await db_session.flush()

        # Grant signup bonus
        await grant_credits(db_session, user.id, 50, TransactionType.SIGNUP_BONUS)
        await db_session.commit()

        # Verify balance is 50, not 100
        assert account.balance == 50

        # Check transaction count for signup_bonus type
        result = await db_session.execute(
            select(CreditTransaction).where(
                CreditTransaction.credit_account_id == account.id,
                CreditTransaction.transaction_type == TransactionType.SIGNUP_BONUS,
            )
        )
        txns = result.scalars().all()
        assert len(txns) == 1


# ---------------------------------------------------------------------------
# AUTH_ENABLED=false (open access)
# ---------------------------------------------------------------------------


class TestAuthDisabled:
    @pytest.mark.asyncio
    async def test_get_current_user_returns_none_when_disabled(self):
        """When AUTH_ENABLED=false, get_current_user should return None."""
        from app.auth.dependencies import get_current_user

        with patch("app.auth.dependencies.get_settings") as mock_settings:
            s = MagicMock()
            s.AUTH_ENABLED = False
            mock_settings.return_value = s

            request = MagicMock()
            session = MagicMock()
            result = await get_current_user(request, session)
            assert result is None

    @pytest.mark.asyncio
    async def test_require_credits_noop_when_disabled(self):
        """When AUTH_ENABLED=false, require_credits should be a no-op."""
        from app.auth.dependencies import require_credits

        dep = require_credits(5)

        with patch("app.auth.dependencies.get_settings") as mock_settings:
            s = MagicMock()
            s.AUTH_ENABLED = False
            mock_settings.return_value = s

            request = MagicMock()
            session = MagicMock()
            # Should not raise
            await dep(request, user=None, session=session)
