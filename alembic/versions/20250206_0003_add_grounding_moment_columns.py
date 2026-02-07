"""Add grounding_data_json and moment_data_json columns to timepoints.

Revision ID: 0003
Revises: 0002
Create Date: 2025-02-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add grounding and moment JSON columns."""
    op.add_column("timepoints", sa.Column("grounding_data_json", sa.JSON(), nullable=True))
    op.add_column("timepoints", sa.Column("moment_data_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove grounding and moment JSON columns."""
    op.drop_column("timepoints", "moment_data_json")
    op.drop_column("timepoints", "grounding_data_json")
