"""Add chat_sessions table for character conversations.

Revision ID: 0002
Revises: 0001
Create Date: 2024-12-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create chat_sessions table."""
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "timepoint_id",
            sa.String(36),
            sa.ForeignKey("timepoints.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("character_name", sa.String(100), nullable=False, index=True),
        sa.Column("messages_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # Create composite index for common queries
    op.create_index(
        "ix_chat_sessions_timepoint_character",
        "chat_sessions",
        ["timepoint_id", "character_name"],
    )


def downgrade() -> None:
    """Drop chat_sessions table."""
    op.drop_index("ix_chat_sessions_timepoint_character", table_name="chat_sessions")
    op.drop_table("chat_sessions")
