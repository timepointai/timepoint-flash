"""Storage service — main orchestrator for blob I/O.

Handles writing, reconstructing, and deleting timepoint blobs.

Examples:
    >>> from app.storage.service import StorageService
    >>> service = StorageService.from_config(config)
    >>> blob_path = await service.write_blob(timepoint, session)
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.storage.backends.base import StorageBackend
from app.storage.backends.local import LocalStorageBackend
from app.storage.config import StorageConfig
from app.storage.index_html import generate_index_html
from app.storage.manifest import BlobManifest, FileEntry, build_manifest
from app.storage.naming import generate_folder_path

logger = logging.getLogger(__name__)


class StorageService:
    """Main orchestrator for blob storage operations.

    Attributes:
        config: Storage configuration.
        backend: Storage backend for I/O.
    """

    def __init__(self, config: StorageConfig, backend: StorageBackend | None = None) -> None:
        self.config = config
        self.backend = backend or LocalStorageBackend()

    @classmethod
    def from_config(cls, config: StorageConfig) -> "StorageService":
        """Create a StorageService from config."""
        return cls(config=config, backend=LocalStorageBackend())

    async def write_blob(
        self,
        timepoint: Any,
        generation_logs: list[Any] | None = None,
        sequence_members: list[dict[str, Any]] | None = None,
    ) -> tuple[str, str]:
        """Write a complete blob folder for a timepoint.

        Args:
            timepoint: Timepoint ORM model.
            generation_logs: Optional list of GenerationLog models.
            sequence_members: Optional list of sequence member dicts for sequence.json.

        Returns:
            Tuple of (full_path, folder_name).
        """
        full_path, folder_name = generate_folder_path(
            root=self.config.root,
            query=timepoint.query,
        )

        file_entries: list[FileEntry] = []

        # 1. Decode and write image
        if timepoint.image_base64:
            image_data = base64.b64decode(timepoint.image_base64)
            # Detect format
            ext = "png" if timepoint.image_base64.startswith("iVBOR") else "jpg"
            mime = "image/png" if ext == "png" else "image/jpeg"
            image_path = f"{full_path}/image.{ext}"
            await self.backend.write_file(image_path, image_data)
            file_entries.append(FileEntry(
                filename=f"image.{ext}",
                mime_type=mime,
                size_bytes=len(image_data),
                sha256=hashlib.sha256(image_data).hexdigest(),
            ))

        # 2. Write JSON sidecars
        json_files = [
            ("metadata.json", timepoint.metadata_json),
            ("scene.json", timepoint.scene_data_json),
            ("characters.json", timepoint.character_data_json),
            ("dialog.json", timepoint.dialog_json),
        ]
        # Optional JSON fields
        if timepoint.grounding_data_json:
            json_files.append(("grounding.json", timepoint.grounding_data_json))
        if timepoint.moment_data_json:
            json_files.append(("moment.json", timepoint.moment_data_json))

        for filename, data in json_files:
            if data is not None:
                text = json.dumps(data, indent=2, default=str)
                text_bytes = text.encode("utf-8")
                await self.backend.write_text(f"{full_path}/{filename}", text)
                file_entries.append(FileEntry(
                    filename=filename,
                    mime_type="application/json",
                    size_bytes=len(text_bytes),
                    sha256=hashlib.sha256(text_bytes).hexdigest(),
                ))

        # 3. Write image prompt text
        if timepoint.image_prompt:
            prompt_bytes = timepoint.image_prompt.encode("utf-8")
            await self.backend.write_text(f"{full_path}/image_prompt.txt", timepoint.image_prompt)
            file_entries.append(FileEntry(
                filename="image_prompt.txt",
                mime_type="text/plain",
                size_bytes=len(prompt_bytes),
                sha256=hashlib.sha256(prompt_bytes).hexdigest(),
            ))

        # 4. Write generation log
        if generation_logs:
            log_data = []
            for log in generation_logs:
                if hasattr(log, "to_dict"):
                    log_data.append(log.to_dict())
                else:
                    log_data.append({
                        "step": getattr(log, "step", "unknown"),
                        "status": getattr(log, "status", "unknown"),
                        "latency_ms": getattr(log, "latency_ms", None),
                        "model_used": getattr(log, "model_used", None),
                        "error_message": getattr(log, "error_message", None),
                    })
            log_text = json.dumps(log_data, indent=2, default=str)
            log_bytes = log_text.encode("utf-8")
            await self.backend.write_text(f"{full_path}/generation_log.json", log_text)
            file_entries.append(FileEntry(
                filename="generation_log.json",
                mime_type="application/json",
                size_bytes=len(log_bytes),
                sha256=hashlib.sha256(log_bytes).hexdigest(),
            ))

        # 5. Write provenance stub
        provenance_data = {
            "digital_source_type": "trainedAlgorithmicMedia",
            "generator": "timepoint-flash",
            "c2pa": None,
            "iptc": {
                "digital_source_type": "trainedAlgorithmicMedia",
            },
        }
        prov_text = json.dumps(provenance_data, indent=2)
        prov_bytes = prov_text.encode("utf-8")
        await self.backend.write_text(f"{full_path}/provenance.json", prov_text)
        file_entries.append(FileEntry(
            filename="provenance.json",
            mime_type="application/json",
            size_bytes=len(prov_bytes),
            sha256=hashlib.sha256(prov_bytes).hexdigest(),
        ))

        # 6. Write sequence.json if part of a sequence
        if sequence_members or getattr(timepoint, "sequence_id", None):
            seq_data = {
                "sequence_id": getattr(timepoint, "sequence_id", None),
                "members": sequence_members or [],
            }
            seq_text = json.dumps(seq_data, indent=2, default=str)
            seq_bytes = seq_text.encode("utf-8")
            await self.backend.write_text(f"{full_path}/sequence.json", seq_text)
            file_entries.append(FileEntry(
                filename="sequence.json",
                mime_type="application/json",
                size_bytes=len(seq_bytes),
                sha256=hashlib.sha256(seq_bytes).hexdigest(),
            ))

        # 7. Build and write manifest
        log_steps = []
        total_latency = None
        if generation_logs:
            log_steps = [getattr(log, "step", "unknown") for log in generation_logs]
            latencies = [getattr(log, "latency_ms", 0) or 0 for log in generation_logs]
            total_latency = sum(latencies) if latencies else None

        manifest = build_manifest(
            timepoint=timepoint,
            folder_name=folder_name,
            full_path=full_path,
            file_entries=file_entries,
            generation_log_steps=log_steps,
            total_latency_ms=total_latency,
        )

        manifest_text = manifest.model_dump_json(indent=2)
        manifest_bytes = manifest_text.encode("utf-8")
        await self.backend.write_text(f"{full_path}/manifest.json", manifest_text)

        # Add manifest itself to entries (for completeness, but it won't be in its own listing)
        # We don't re-build — manifest is already written

        # 8. Write index.html
        html = generate_index_html(manifest)
        await self.backend.write_text(f"{full_path}/index.html", html)

        logger.info(f"Blob written: {full_path} ({len(file_entries)} files)")
        return full_path, folder_name

    async def reconstruct_blob(
        self,
        timepoint: Any,
        generation_logs: list[Any] | None = None,
        sequence_members: list[dict[str, Any]] | None = None,
    ) -> tuple[str, str]:
        """Reconstruct (rewrite) a blob folder for an existing timepoint.

        This overwrites any existing blob at the same path.

        Args:
            timepoint: Timepoint ORM model.
            generation_logs: Optional generation logs.
            sequence_members: Optional sequence member dicts.

        Returns:
            Tuple of (full_path, folder_name).
        """
        # If blob already exists, delete it first
        if hasattr(timepoint, "blob_path") and timepoint.blob_path:
            if await self.backend.exists(timepoint.blob_path):
                await self.backend.delete_directory(timepoint.blob_path)

        return await self.write_blob(timepoint, generation_logs, sequence_members)

    async def delete_blob(
        self,
        timepoint: Any,
        soft: bool = True,
    ) -> str | None:
        """Delete a blob folder.

        Args:
            timepoint: Timepoint ORM model with blob_path.
            soft: If True, move to .trash/. If False, permanently delete.

        Returns:
            Trash path if soft-deleted, None if hard-deleted.
        """
        blob_path = getattr(timepoint, "blob_path", None)
        if not blob_path:
            return None

        if not await self.backend.exists(blob_path):
            return None

        if soft:
            # Move to .trash/{date}/
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            folder_name = getattr(timepoint, "blob_folder_name", "unknown")
            trash_path = f"{self.config.root}/.trash/{today}/{folder_name}"
            await self.backend.move_directory(blob_path, trash_path)
            logger.info(f"Blob soft-deleted: {blob_path} -> {trash_path}")
            return trash_path
        else:
            await self.backend.delete_directory(blob_path)
            logger.info(f"Blob hard-deleted: {blob_path}")
            return None
