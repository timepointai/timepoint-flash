"""Blob manifest schema and builder.

Defines the BlobManifest and FileEntry Pydantic models,
plus a build_manifest() function that constructs a manifest
from a Timepoint database model.

Examples:
    >>> from app.storage.manifest import build_manifest
    >>> manifest = build_manifest(timepoint, folder_name, full_path, file_entries)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FileEntry(BaseModel):
    """A single file in the blob folder."""

    filename: str
    mime_type: str
    size_bytes: int = 0
    sha256: str | None = None


class SequenceInfo(BaseModel):
    """Sequence linking metadata."""

    sequence_id: str | None = None
    position: int = 1
    parent_timepoint_id: str | None = None


class ProvenanceInfo(BaseModel):
    """Generation provenance and attribution."""

    text_model: str | None = None
    image_model: str | None = None
    generator: str = "timepoint-flash"
    generator_version: str = ""
    generated_at: str | None = None
    digital_source_type: str = "trainedAlgorithmicMedia"
    pipeline_steps: list[str] = Field(default_factory=list)
    total_latency_ms: int | None = None


class ContentFlags(BaseModel):
    """Content moderation flags."""

    nsfw_flag: bool = False
    nsfw_score: float | None = None


class Attribution(BaseModel):
    """User attribution metadata."""

    created_by: str | None = None
    api_source: str | None = None


class AccessInfo(BaseModel):
    """Access tracking metadata."""

    view_count: int = 0
    last_accessed_at: str | None = None


class TemporalInfo(BaseModel):
    """Temporal context for the timepoint."""

    year: int | None = None
    month: int | None = None
    era: str | None = None
    location: str | None = None


class BlobManifest(BaseModel):
    """Full manifest for a blob folder.

    Contains complete provenance, file inventory, and metadata
    for a self-contained timepoint blob.
    """

    manifest_version: str = "1.0"
    timepoint_id: str
    slug: str
    query: str
    folder_name: str
    full_path: str

    temporal: TemporalInfo = Field(default_factory=TemporalInfo)
    provenance: ProvenanceInfo = Field(default_factory=ProvenanceInfo)
    sequence: SequenceInfo = Field(default_factory=SequenceInfo)

    files: list[FileEntry] = Field(default_factory=list)
    total_size_bytes: int = 0

    content_flags: ContentFlags = Field(default_factory=ContentFlags)
    render_type: str = "image"
    synthetic_camera: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    attribution: Attribution = Field(default_factory=Attribution)
    access: AccessInfo = Field(default_factory=AccessInfo)
    generation_version: int = 1

    stubs: dict[str, str] = Field(default_factory=lambda: {
        "cloud_storage": "coming soon",
        "c2pa_credentials": "coming soon",
        "vr_spatial_render": "coming soon",
        "nsfw_detection": "coming soon",
        "video_render": "coming soon",
    })


def build_manifest(
    timepoint: Any,
    folder_name: str,
    full_path: str,
    file_entries: list[FileEntry],
    generation_log_steps: list[str] | None = None,
    total_latency_ms: int | None = None,
) -> BlobManifest:
    """Build a BlobManifest from a Timepoint model instance.

    Args:
        timepoint: Timepoint ORM model.
        folder_name: Blob folder name.
        full_path: Full filesystem path.
        file_entries: List of files written to the blob.
        generation_log_steps: Pipeline step names.
        total_latency_ms: Total pipeline latency.

    Returns:
        Populated BlobManifest.
    """
    from app import __version__

    total_size = sum(f.size_bytes for f in file_entries)

    # Extract synthetic camera from metadata
    synthetic_camera: dict[str, Any] = {}
    if timepoint.metadata_json and isinstance(timepoint.metadata_json, dict):
        synthetic_camera = timepoint.metadata_json.get("synthetic_camera", {})

    # Extract tags
    tags: list[str] = []
    if hasattr(timepoint, "tags_json") and timepoint.tags_json:
        tags = timepoint.tags_json if isinstance(timepoint.tags_json, list) else []

    generated_at = None
    if timepoint.created_at:
        if isinstance(timepoint.created_at, datetime):
            generated_at = timepoint.created_at.isoformat()
        else:
            generated_at = str(timepoint.created_at)

    return BlobManifest(
        timepoint_id=timepoint.id,
        slug=timepoint.slug,
        query=timepoint.query,
        folder_name=folder_name,
        full_path=full_path,
        temporal=TemporalInfo(
            year=timepoint.year,
            month=timepoint.month,
            era=timepoint.era,
            location=timepoint.location,
        ),
        provenance=ProvenanceInfo(
            text_model=timepoint.text_model_used,
            image_model=timepoint.image_model_used,
            generator="timepoint-flash",
            generator_version=__version__,
            generated_at=generated_at,
            pipeline_steps=generation_log_steps or [],
            total_latency_ms=total_latency_ms,
        ),
        sequence=SequenceInfo(
            sequence_id=getattr(timepoint, "sequence_id", None),
            parent_timepoint_id=timepoint.parent_id,
        ),
        files=file_entries,
        total_size_bytes=total_size,
        content_flags=ContentFlags(
            nsfw_flag=getattr(timepoint, "nsfw_flag", False),
        ),
        render_type=getattr(timepoint, "render_type", "image") or "image",
        synthetic_camera=synthetic_camera,
        tags=tags,
        attribution=Attribution(
            created_by=getattr(timepoint, "created_by", None),
            api_source=getattr(timepoint, "api_source", None),
        ),
        access=AccessInfo(
            view_count=getattr(timepoint, "view_count", 0) or 0,
            last_accessed_at=(
                getattr(timepoint, "last_accessed_at", None).isoformat()
                if getattr(timepoint, "last_accessed_at", None)
                else None
            ),
        ),
        generation_version=getattr(timepoint, "generation_version", 1) or 1,
    )
