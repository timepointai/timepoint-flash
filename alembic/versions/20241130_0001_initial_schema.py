"""Initial schema for TIMEPOINT Flash v2.0.

Revision ID: 0001
Revises: None
Create Date: 2024-11-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""
    # Create timepoints table
    op.create_table(
        "timepoints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("query", sa.Text(), nullable=False, index=True),
        sa.Column("slug", sa.String(150), unique=True, index=True),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "completed", "failed", name="timepointstatus"),
            default="pending",
            index=True,
        ),
        # Temporal fields
        sa.Column("year", sa.Integer(), nullable=True, index=True),
        sa.Column("month", sa.Integer(), nullable=True),
        sa.Column("day", sa.Integer(), nullable=True),
        sa.Column("season", sa.String(20), nullable=True),
        sa.Column("time_of_day", sa.String(50), nullable=True),
        sa.Column("era", sa.String(50), nullable=True),
        # Location
        sa.Column("location", sa.Text(), nullable=True),
        # JSON data fields
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("character_data_json", sa.JSON(), nullable=True),
        sa.Column("scene_data_json", sa.JSON(), nullable=True),
        sa.Column("dialog_json", sa.JSON(), nullable=True),
        # Image generation
        sa.Column("image_prompt", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("image_base64", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        # Self-referential relationship
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("timepoints.id"), nullable=True),
        # Error tracking
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    # Create generation_logs table
    op.create_table(
        "generation_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "timepoint_id",
            sa.String(36),
            sa.ForeignKey("timepoints.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("step", sa.String(50), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("input_data", sa.JSON(), nullable=True),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("provider", sa.String(20), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("token_usage", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create indexes for common queries
    op.create_index("ix_timepoints_status_created", "timepoints", ["status", "created_at"])
    op.create_index("ix_timepoints_year_location", "timepoints", ["year", "location"])
    op.create_index("ix_generation_logs_step_status", "generation_logs", ["step", "status"])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_index("ix_generation_logs_step_status", table_name="generation_logs")
    op.drop_index("ix_timepoints_year_location", table_name="timepoints")
    op.drop_index("ix_timepoints_status_created", table_name="timepoints")
    op.drop_table("generation_logs")
    op.drop_table("timepoints")
    op.execute("DROP TYPE IF EXISTS timepointstatus")
