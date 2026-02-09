"""Storage configuration model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StorageConfig(BaseModel):
    """Configuration for blob storage.

    Attributes:
        enabled: Whether blob storage is active.
        root: Root directory for blob output.
    """

    enabled: bool = Field(default=False, description="Enable blob storage")
    root: str = Field(default="./output/timepoints", description="Blob storage root directory")
