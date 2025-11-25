"""change_image_url_columns_to_text

Revision ID: 32c5060e05a7
Revises: 
Create Date: 2025-10-27 19:00:28.146635+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '32c5060e05a7'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Change image_url and segmented_image_url from VARCHAR(500) to TEXT
    # to support large base64 encoded image data
    op.alter_column('timepoints', 'image_url',
                    existing_type=sa.String(500),
                    type_=sa.Text(),
                    existing_nullable=True)
    op.alter_column('timepoints', 'segmented_image_url',
                    existing_type=sa.String(500),
                    type_=sa.Text(),
                    existing_nullable=True)


def downgrade() -> None:
    # Revert back to VARCHAR(500)
    op.alter_column('timepoints', 'segmented_image_url',
                    existing_type=sa.Text(),
                    type_=sa.String(500),
                    existing_nullable=True)
    op.alter_column('timepoints', 'image_url',
                    existing_type=sa.Text(),
                    type_=sa.String(500),
                    existing_nullable=True)
