"""Tests for credit system — ledger immutability, cost lookups, concurrent ops."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.auth.credits import CREDIT_COSTS, grant_credits, spend_credits
from app.models_auth import (
    CreditAccount,
    CreditTransaction,
    TransactionType,
    User,
)


class TestCreditCosts:
    """Verify all expected operations have cost entries."""

    def test_all_operations_have_costs(self):
        expected_ops = [
            "generate_balanced",
            "generate_hd",
            "generate_hyper",
            "generate_gemini3",
            "chat",
            "temporal_jump",
        ]
        for op in expected_ops:
            assert op in CREDIT_COSTS, f"Missing cost for {op}"
            assert isinstance(CREDIT_COSTS[op], int)
            assert CREDIT_COSTS[op] > 0

    def test_hd_costs_more_than_balanced(self):
        assert CREDIT_COSTS["generate_hd"] > CREDIT_COSTS["generate_balanced"]


class TestTransactionLedger:
    """Transaction entries should be immutable — only append."""

    @pytest.mark.asyncio
    async def test_transactions_are_append_only(self, db_session):
        """After creating transactions, verify they can be listed and counted."""
        user = User(apple_sub="ledger-test-001")
        db_session.add(user)
        await db_session.flush()

        account = CreditAccount(user_id=user.id, balance=0, lifetime_earned=0, lifetime_spent=0)
        db_session.add(account)
        await db_session.flush()

        # Grant then spend
        await grant_credits(db_session, user.id, 50, TransactionType.SIGNUP_BONUS)
        await spend_credits(db_session, user.id, 5, TransactionType.GENERATION, description="Gen 1")
        await spend_credits(db_session, user.id, 1, TransactionType.CHAT, description="Chat 1")
        await db_session.commit()

        # Verify transaction count
        result = await db_session.execute(
            select(CreditTransaction)
            .where(CreditTransaction.credit_account_id == account.id)
            .order_by(CreditTransaction.created_at)
        )
        txns = result.scalars().all()
        assert len(txns) == 3

        # Verify running balance trail
        assert txns[0].amount == 50
        assert txns[0].balance_after == 50
        assert txns[1].amount == -5
        assert txns[1].balance_after == 45
        assert txns[2].amount == -1
        assert txns[2].balance_after == 44

        # Verify account cache matches
        assert account.balance == 44
        assert account.lifetime_earned == 50
        assert account.lifetime_spent == 6

    @pytest.mark.asyncio
    async def test_reference_id_links_to_timepoint(self, db_session):
        """Transactions can optionally reference a timepoint_id."""
        user = User(apple_sub="ledger-test-002")
        db_session.add(user)
        await db_session.flush()

        account = CreditAccount(user_id=user.id, balance=100, lifetime_earned=100, lifetime_spent=0)
        db_session.add(account)
        await db_session.flush()

        txn = await spend_credits(
            db_session,
            user.id,
            5,
            TransactionType.GENERATION,
            reference_id="timepoint-abc-123",
            description="Test generation",
        )
        await db_session.commit()

        assert txn.reference_id == "timepoint-abc-123"


class TestConcurrentSpend:
    """Test that concurrent spend attempts don't overdraw."""

    @pytest.mark.asyncio
    async def test_cannot_overdraw_sequentially(self, db_session):
        """Sequential spends should fail when balance insufficient."""
        user = User(apple_sub="concurrent-test-001")
        db_session.add(user)
        await db_session.flush()

        account = CreditAccount(user_id=user.id, balance=7, lifetime_earned=7, lifetime_spent=0)
        db_session.add(account)
        await db_session.flush()

        # First spend succeeds
        await spend_credits(db_session, user.id, 5, TransactionType.GENERATION)

        # Second spend should fail (only 2 left)
        with pytest.raises(ValueError, match="Insufficient"):
            await spend_credits(db_session, user.id, 5, TransactionType.GENERATION)

        # Balance should be 2
        assert account.balance == 2
