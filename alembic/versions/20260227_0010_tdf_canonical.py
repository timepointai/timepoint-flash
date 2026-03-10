"""Replace 7 JSON columns with canonical tdf_payload.

Adds tdf_payload (JSON), tdf_hash (VARCHAR 64, indexed), tdf_version.
Migrates existing data from the old columns into tdf_payload, then drops
scene_data_json, character_data_json, dialog_json,
grounding_data_json, moment_data_json, metadata_json, image_prompt.

Revision ID: 0010
Revises: 0009
Create Date: 2026-02-27
"""

from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    # Add new TDF columns
    op.add_column("timepoints", sa.Column("tdf_payload", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("timepoints", sa.Column("tdf_hash", sa.String(64), nullable=False, server_default=""))
    op.add_column("timepoints", sa.Column("tdf_version", sa.String(10), nullable=False, server_default="1.0.0"))
    op.create_index("ix_timepoints_tdf_hash", "timepoints", ["tdf_hash"])

    # --- DATA MIGRATION ---
    # Populate tdf_payload from the old columns before dropping them.
    # This uses raw SQL to build a JSON object from the existing columns.
    # Works for PostgreSQL; SQLite (used in tests) handles JSON differently,
    # so we use a Python-based migration via a helper connection.
    conn = op.get_bind()

    # Fetch all timepoints that have data in old columns
    results = conn.execute(
        sa.text(
            "SELECT id, metadata_json, character_data_json, scene_data_json, "
            "dialog_json, grounding_data_json, moment_data_json, image_prompt "
            "FROM timepoints"
        )
    )

    import hashlib
    import json

    for row in results:
        payload = {}
        # metadata_json contained timeline, scene, moment, camera, graph sub-keys
        if row.metadata_json:
            meta = row.metadata_json if isinstance(row.metadata_json, dict) else json.loads(row.metadata_json)
            if "graph" in meta:
                payload["graph_data"] = meta["graph"]
            if "camera" in meta:
                payload["camera_data"] = meta["camera"]
        if row.scene_data_json:
            scene = row.scene_data_json if isinstance(row.scene_data_json, dict) else json.loads(row.scene_data_json)
            payload["scene_data"] = scene
        if row.character_data_json:
            chars = row.character_data_json if isinstance(row.character_data_json, dict) else json.loads(row.character_data_json)
            payload["character_data"] = chars
        if row.dialog_json:
            dialog = row.dialog_json if isinstance(row.dialog_json, list) else json.loads(row.dialog_json)
            payload["dialog"] = dialog
        if row.grounding_data_json:
            grounding = row.grounding_data_json if isinstance(row.grounding_data_json, dict) else json.loads(row.grounding_data_json)
            payload["grounding_data"] = grounding
        if row.moment_data_json:
            moment = row.moment_data_json if isinstance(row.moment_data_json, dict) else json.loads(row.moment_data_json)
            payload["moment_data"] = moment
        if row.image_prompt:
            payload["image_prompt"] = row.image_prompt

        if payload:
            canonical = json.dumps(payload, sort_keys=True, default=str)
            tdf_hash = hashlib.sha256(canonical.encode()).hexdigest()
            conn.execute(
                sa.text("UPDATE timepoints SET tdf_payload = :payload, tdf_hash = :hash WHERE id = :id"),
                {"payload": json.dumps(payload), "hash": tdf_hash, "id": row.id},
            )

    # Drop old JSON columns
    op.drop_column("timepoints", "scene_data_json")
    op.drop_column("timepoints", "character_data_json")
    op.drop_column("timepoints", "dialog_json")
    op.drop_column("timepoints", "grounding_data_json")
    op.drop_column("timepoints", "moment_data_json")
    op.drop_column("timepoints", "metadata_json")
    op.drop_column("timepoints", "image_prompt")


def downgrade() -> None:
    # Re-add old columns
    op.add_column("timepoints", sa.Column("image_prompt", sa.Text(), nullable=True))
    op.add_column("timepoints", sa.Column("metadata_json", sa.JSON(), nullable=True))
    op.add_column("timepoints", sa.Column("moment_data_json", sa.JSON(), nullable=True))
    op.add_column("timepoints", sa.Column("grounding_data_json", sa.JSON(), nullable=True))
    op.add_column("timepoints", sa.Column("dialog_json", sa.JSON(), nullable=True))
    op.add_column("timepoints", sa.Column("character_data_json", sa.JSON(), nullable=True))
    op.add_column("timepoints", sa.Column("scene_data_json", sa.JSON(), nullable=True))

    # Drop TDF columns
    op.drop_index("ix_timepoints_tdf_hash", table_name="timepoints")
    op.drop_column("timepoints", "tdf_version")
    op.drop_column("timepoints", "tdf_hash")
    op.drop_column("timepoints", "tdf_payload")
