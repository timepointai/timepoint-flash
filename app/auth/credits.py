"""Credit balance management — check, spend, grant.

All operations are atomic within the caller's DB session.
CreditTransaction is an append-only immutable ledger.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_auth import CreditAccount, CreditTransaction, TransactionType

logger = logging.getLogger(__name__)

# Credit costs per operation
CREDIT_COSTS: dict[str, int] = {
    "generate_balanced": 5,
    "generate_hd": 10,
    "generate_hyper": 5,
    "generate_gemini3": 5,
    "chat": 1,
    "temporal_jump": 2,
}


async def _get_account(session: AsyncSession, user_id: str) -> CreditAccount:
    """Fetch the credit account for a user.

    Raises:
        ValueError: If no credit account exists.
    """
    result = await session.execute(select(CreditAccount).where(CreditAccount.user_id == user_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise ValueError(f"No credit account for user {user_id}")
    return account


async def check_balance(session: AsyncSession, user_id: str, cost: int) -> bool:
    """Check whether a user has sufficient credits.

    Args:
        session: DB session.
        user_id: User UUID.
        cost: Required credits.

    Returns:
        True if balance >= cost.
    """
    account = await _get_account(session, user_id)
    return account.balance >= cost


async def spend_credits(
    session: AsyncSession,
    user_id: str,
    cost: int,
    transaction_type: TransactionType,
    reference_id: str | None = None,
    description: str | None = None,
) -> CreditTransaction:
    """Deduct credits and record a ledger entry.

    Args:
        session: DB session (caller must commit).
        user_id: User UUID.
        cost: Positive integer to deduct.
        transaction_type: Type of charge.
        reference_id: Optional timepoint_id or similar.
        description: Human-readable note.

    Returns:
        The created CreditTransaction.

    Raises:
        ValueError: If insufficient balance.
    """
    account = await _get_account(session, user_id)

    if account.balance < cost:
        raise ValueError(f"Insufficient credits: have {account.balance}, need {cost}")

    account.balance -= cost
    account.lifetime_spent += cost

    txn = CreditTransaction(
        credit_account_id=account.id,
        amount=-cost,
        balance_after=account.balance,
        transaction_type=transaction_type,
        reference_id=reference_id,
        description=description,
    )
    session.add(txn)
    return txn


async def grant_credits(
    session: AsyncSession,
    user_id: str,
    amount: int,
    transaction_type: TransactionType,
    description: str | None = None,
) -> CreditTransaction:
    """Add credits and record a ledger entry.

    Args:
        session: DB session (caller must commit).
        user_id: User UUID.
        amount: Positive integer to add.
        transaction_type: Type of grant (signup_bonus, admin_grant, etc.).
        description: Human-readable note.

    Returns:
        The created CreditTransaction.
    """
    account = await _get_account(session, user_id)

    account.balance += amount
    account.lifetime_earned += amount

    txn = CreditTransaction(
        credit_account_id=account.id,
        amount=amount,
        balance_after=account.balance,
        transaction_type=transaction_type,
        description=description,
    )
    session.add(txn)
    return txn
