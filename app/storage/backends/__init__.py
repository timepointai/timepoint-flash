"""Storage backends for blob I/O."""

from app.storage.backends.base import StorageBackend
from app.storage.backends.local import LocalStorageBackend

__all__ = ["StorageBackend", "LocalStorageBackend"]
