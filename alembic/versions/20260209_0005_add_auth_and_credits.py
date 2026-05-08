"""Add auth and credits tables, add user_id to timepoints.

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create auth/credit tables and add user_id FK to timepoints."""

    # --- Users ---
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("apple_sub", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_users_apple_sub", "users", ["apple_sub"], unique=True)

    # --- Credit Accounts ---
    op.create_table(
        "credit_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("balance", sa.Integer(), nullable=False, server_default=sa.text("50")),
        sa.Column("lifetime_earned", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("lifetime_spent", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # --- Credit Transactions (immutable ledger) ---
    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "credit_account_id",
            sa.String(36),
            sa.ForeignKey("credit_accounts.id"),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column(
            "transaction_type",
            sa.Enum(
                "signup_bonus",
                "generation",
                "chat",
                "temporal",
                "admin_grant",
                name="transactiontype",
            ),
            nullable=False,
        ),
        sa.Column("reference_id", sa.String(36), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_credit_transactions_credit_account_id",
        "credit_transactions",
        ["credit_account_id"],
    )

    # --- Refresh Tokens ---
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])

    # --- Add user_id FK to timepoints ---
    op.add_column(
        "timepoints",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    )


def downgrade() -> None:
    """Remove auth/credit tables and user_id from timepoints."""
    op.drop_column("timepoints", "user_id")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index(
        "ix_credit_transactions_credit_account_id",
        table_name="credit_transactions",
    )
    op.drop_table("credit_transactions")
    op.drop_table("credit_accounts")
    op.drop_index("ix_users_apple_sub", table_name="users")
    op.drop_table("users")
