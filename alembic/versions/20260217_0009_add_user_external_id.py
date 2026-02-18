"""Add external_id column to users table.

Supports Auth0 and other external identity providers
alongside the existing Apple Sign-In (apple_sub) column.

Revision ID: 0009
Revises: 0008
Create Date: 2026-02-17
"""

from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "external_id",
            sa.String(255),
            nullable=True,
            comment="Auth0 sub or other external identity provider ID",
        ),
    )
    op.create_index("ix_users_external_id", "users", ["external_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_external_id", table_name="users")
    op.drop_column("users", "external_id")
