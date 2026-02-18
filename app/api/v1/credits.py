"""Credits API endpoints — balance, history, costs.

Endpoints:
    GET /api/v1/credits/balance — Current credit balance
    GET /api/v1/credits/history — Paginated transaction ledger
    GET /api/v1/credits/costs   — Credit cost table
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.credits import CREDIT_COSTS, grant_credits
from app.auth.dependencies import get_current_user, require_admin_key
from app.auth.schemas import (
    AdminGrantRequest,
    AdminGrantResponse,
    CreditBalanceResponse,
    CreditCostsResponse,
    CreditTransactionResponse,
)
from app.database import get_db_session
from app.models_auth import CreditAccount, CreditTransaction, TransactionType, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("/balance", response_model=CreditBalanceResponse)
async def get_balance(
    user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> CreditBalanceResponse:
    """Return the current user's credit balance."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    result = await session.execute(
        select(CreditAccount).where(CreditAccount.user_id == user.id)
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Credit account not found")

    return CreditBalanceResponse(
        balance=account.balance,
        lifetime_earned=account.lifetime_earned,
        lifetime_spent=account.lifetime_spent,
    )


@router.get("/history", response_model=list[CreditTransactionResponse])
async def get_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[CreditTransactionResponse]:
    """Return paginated credit transaction history."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    # Get account
    acct_result = await session.execute(
        select(CreditAccount).where(CreditAccount.user_id == user.id)
    )
    account = acct_result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Credit account not found")

    result = await session.execute(
        select(CreditTransaction)
        .where(CreditTransaction.credit_account_id == account.id)
        .order_by(CreditTransaction.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    transactions = result.scalars().all()

    return [
        CreditTransactionResponse(
            amount=t.amount,
            balance_after=t.balance_after,
            type=t.transaction_type.value,
            description=t.description,
            created_at=t.created_at,
        )
        for t in transactions
    ]


@router.post("/admin/grant", response_model=AdminGrantResponse)
async def admin_grant(
    request: AdminGrantRequest,
    session: AsyncSession = Depends(get_db_session),
    _admin: None = Depends(require_admin_key),
) -> AdminGrantResponse:
    """Grant credits to any user by user ID. Requires X-Admin-Key header."""
    # Verify user exists
    result = await session.execute(
        select(User).where(User.id == request.user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Resolve transaction type (billing sends specific types like stripe_purchase)
    txn_type = TransactionType.ADMIN_GRANT
    if request.transaction_type:
        try:
            txn_type = TransactionType(request.transaction_type)
        except ValueError:
            pass  # Fall back to ADMIN_GRANT for unknown types

    await grant_credits(
        session,
        request.user_id,
        request.amount,
        txn_type,
        description=request.description,
    )
    await session.commit()

    # Fetch updated balance
    acct_result = await session.execute(
        select(CreditAccount).where(CreditAccount.user_id == request.user_id)
    )
    account = acct_result.scalar_one()

    return AdminGrantResponse(balance=account.balance, granted=request.amount)


@router.get("/costs", response_model=CreditCostsResponse)
async def get_costs() -> CreditCostsResponse:
    """Return the credit cost table so clients know prices."""
    return CreditCostsResponse(costs=CREDIT_COSTS)
