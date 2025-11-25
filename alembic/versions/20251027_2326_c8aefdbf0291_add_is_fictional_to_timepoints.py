"""add_is_fictional_to_timepoints

Revision ID: c8aefdbf0291
Revises: 32c5060e05a7
Create Date: 2025-10-27 23:26:33.295822+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8aefdbf0291'
down_revision: Union[str, None] = '32c5060e05a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_fictional column to timepoints table
    op.add_column('timepoints', sa.Column('is_fictional', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    # Remove is_fictional column from timepoints table
    op.drop_column('timepoints', 'is_fictional')
