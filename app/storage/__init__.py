"""Blob storage package for TIMEPOINT Flash.

Provides asset management for generated timepoints, including
folder creation, manifest generation, and file I/O.

Examples:
    >>> from app.storage import StorageService, StorageConfig
    >>> service = StorageService(config=StorageConfig())
    >>> blob_path = await service.write_blob(timepoint)
"""

from app.storage.config import StorageConfig
from app.storage.manifest import BlobManifest, FileEntry
from app.storage.naming import generate_folder_name, generate_folder_path, sanitize_slug
from app.storage.service import StorageService

__all__ = [
    "BlobManifest",
    "FileEntry",
    "StorageConfig",
    "StorageService",
    "generate_folder_name",
    "generate_folder_path",
    "sanitize_slug",
]
