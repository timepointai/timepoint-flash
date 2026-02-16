"""Add billing transaction types and reference_type column.

Revision ID: 0008
Revises: 0007
Create Date: 2026-02-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add billing transaction types and reference_type column."""
    # Add new enum values for PostgreSQL
    # SQLite doesn't have real enums, so these are no-ops there
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'apple_iap'")
        op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'stripe_purchase'")
        op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'subscription_grant'")
        op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'refund'")

    # Add reference_type column to credit_transactions
    op.add_column(
        "credit_transactions",
        sa.Column("reference_type", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    """Remove reference_type column.

    Note: PostgreSQL does not support removing enum values,
    so the transaction type enum values are left in place.
    """
    op.drop_column("credit_transactions", "reference_type")
