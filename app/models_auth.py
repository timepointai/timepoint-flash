"""SQLAlchemy models for authentication and credits.

Defines User, CreditAccount, CreditTransaction (immutable ledger),
and RefreshToken models. Kept separate from models.py to avoid merge conflicts.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class TransactionType(str, Enum):
    """Credit transaction types."""

    SIGNUP_BONUS = "signup_bonus"
    GENERATION = "generation"
    CHAT = "chat"
    TEMPORAL = "temporal"
    ADMIN_GRANT = "admin_grant"
    # Purchase types (used by timepoint-billing module)
    APPLE_IAP = "apple_iap"
    STRIPE_PURCHASE = "stripe_purchase"
    SUBSCRIPTION_GRANT = "subscription_grant"
    REFUND = "refund"


class User(Base):
    """User authenticated via Apple Sign-In."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    apple_sub: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    email: Mapped[str | None] = mapped_column(String(255), default=None)
    display_name: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    credit_account: Mapped["CreditAccount | None"] = relationship(
        back_populates="user", uselist=False
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id!r}, apple_sub={self.apple_sub!r})>"


class CreditAccount(Base):
    """Denormalized credit balance for a user. Can be recomputed from transactions."""

    __tablename__ = "credit_accounts"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), unique=True, nullable=False
    )
    balance: Mapped[int] = mapped_column(Integer, default=50)
    lifetime_earned: Mapped[int] = mapped_column(Integer, default=0)
    lifetime_spent: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="credit_account")
    transactions: Mapped[list["CreditTransaction"]] = relationship(
        back_populates="credit_account"
    )

    def __repr__(self) -> str:
        return f"<CreditAccount(user_id={self.user_id!r}, balance={self.balance})>"


class CreditTransaction(Base):
    """Immutable ledger entry for credit changes. Append-only."""

    __tablename__ = "credit_transactions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    credit_account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("credit_accounts.id"),
        index=True,
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_type: Mapped[TransactionType] = mapped_column(
        SQLEnum(TransactionType, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    reference_id: Mapped[str | None] = mapped_column(String(36), default=None)
    reference_type: Mapped[str | None] = mapped_column(String(50), default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    credit_account: Mapped["CreditAccount"] = relationship(
        back_populates="transactions"
    )

    def __repr__(self) -> str:
        return (
            f"<CreditTransaction(amount={self.amount}, "
            f"type={self.transaction_type.value})>"
        )


class RefreshToken(Base):
    """Hashed refresh token for JWT rotation."""

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def __repr__(self) -> str:
        return f"<RefreshToken(user_id={self.user_id!r}, revoked={self.is_revoked})>"
