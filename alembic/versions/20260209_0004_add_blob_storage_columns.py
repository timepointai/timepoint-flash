"""Add blob storage, soft delete, sequence, and metadata columns to timepoints.

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add blob storage, soft delete, sequence, and stub columns."""
    # Blob storage
    op.add_column("timepoints", sa.Column("blob_folder_name", sa.String(200), nullable=True))
    op.add_column("timepoints", sa.Column("blob_path", sa.Text(), nullable=True))
    op.add_column("timepoints", sa.Column("blob_written_at", sa.DateTime(timezone=True), nullable=True))

    # Soft delete
    op.add_column("timepoints", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("timepoints", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    # NSFW stub
    op.add_column("timepoints", sa.Column("nsfw_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")))

    # Refresh tracking
    op.add_column("timepoints", sa.Column("generation_version", sa.Integer(), nullable=False, server_default=sa.text("1")))
    op.add_column("timepoints", sa.Column("regenerated_from_id", sa.String(36), nullable=True))

    # Sequence grouping
    op.add_column("timepoints", sa.Column("sequence_id", sa.String(36), nullable=True))

    # Analytics stubs
    op.add_column("timepoints", sa.Column("view_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("timepoints", sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("timepoints", sa.Column("api_source", sa.String(50), nullable=True))

    # User attribution stub
    op.add_column("timepoints", sa.Column("created_by", sa.String(100), nullable=True))

    # Render type stub
    op.add_column("timepoints", sa.Column("render_type", sa.String(20), nullable=False, server_default="image"))

    # Tags
    op.add_column("timepoints", sa.Column("tags_json", sa.JSON(), nullable=True))

    # Indexes
    op.create_index("ix_timepoints_is_deleted", "timepoints", ["is_deleted"])
    op.create_index("ix_timepoints_sequence_id", "timepoints", ["sequence_id"])


def downgrade() -> None:
    """Remove blob storage, soft delete, sequence, and stub columns."""
    # Drop indexes first
    op.drop_index("ix_timepoints_sequence_id", table_name="timepoints")
    op.drop_index("ix_timepoints_is_deleted", table_name="timepoints")

    # Drop columns in reverse order
    op.drop_column("timepoints", "tags_json")
    op.drop_column("timepoints", "render_type")
    op.drop_column("timepoints", "created_by")
    op.drop_column("timepoints", "api_source")
    op.drop_column("timepoints", "last_accessed_at")
    op.drop_column("timepoints", "view_count")
    op.drop_column("timepoints", "sequence_id")
    op.drop_column("timepoints", "regenerated_from_id")
    op.drop_column("timepoints", "generation_version")
    op.drop_column("timepoints", "nsfw_flag")
    op.drop_column("timepoints", "deleted_at")
    op.drop_column("timepoints", "is_deleted")
    op.drop_column("timepoints", "blob_written_at")
    op.drop_column("timepoints", "blob_path")
    op.drop_column("timepoints", "blob_folder_name")
