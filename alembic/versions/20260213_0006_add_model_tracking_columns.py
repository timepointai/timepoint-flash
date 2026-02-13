"""Add text_model_used and image_model_used columns to timepoints.

Revision ID: 0006
Revises: 0005
Create Date: 2026-02-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add model tracking columns to timepoints."""
    op.add_column("timepoints", sa.Column("text_model_used", sa.String(200), nullable=True))
    op.add_column("timepoints", sa.Column("image_model_used", sa.String(200), nullable=True))


def downgrade() -> None:
    """Remove model tracking columns from timepoints."""
    op.drop_column("timepoints", "image_model_used")
    op.drop_column("timepoints", "text_model_used")
