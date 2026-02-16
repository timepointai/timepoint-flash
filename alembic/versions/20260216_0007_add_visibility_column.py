"""Add visibility column to timepoints.

Revision ID: 0007
Revises: 0006
Create Date: 2026-02-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add visibility column to timepoints with index."""
    # Create the enum type (checkfirst=True handles PG idempotency;
    # SQLite ignores enum types entirely).
    visibility_enum = sa.Enum("public", "private", name="timepointvisibility", create_constraint=True)
    visibility_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "timepoints",
        sa.Column(
            "visibility",
            visibility_enum,
            nullable=False,
            server_default="public",
        ),
    )
    op.create_index("ix_timepoints_visibility", "timepoints", ["visibility"])


def downgrade() -> None:
    """Remove visibility column and enum type."""
    op.drop_index("ix_timepoints_visibility", table_name="timepoints")
    op.drop_column("timepoints", "visibility")

    # Drop the enum type (PostgreSQL only; SQLite no-ops)
    visibility_enum = sa.Enum(name="timepointvisibility")
    visibility_enum.drop(op.get_bind(), checkfirst=True)
