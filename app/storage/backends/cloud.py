"""Cloud storage backend stub.

Raises NotImplementedError for all operations.
Cloud storage (S3, GCS, etc.) is planned for a future release.
"""

from __future__ import annotations

from app.storage.backends.base import StorageBackend


class CloudStorageBackend(StorageBackend):
    """Cloud storage backend — coming soon.

    This is a stub that raises NotImplementedError for all operations.
    """

    async def write_file(self, path: str, data: bytes) -> None:
        raise NotImplementedError("Cloud storage coming soon")

    async def write_text(self, path: str, text: str) -> None:
        raise NotImplementedError("Cloud storage coming soon")

    async def delete_directory(self, path: str) -> None:
        raise NotImplementedError("Cloud storage coming soon")

    async def exists(self, path: str) -> bool:
        raise NotImplementedError("Cloud storage coming soon")

    async def move_directory(self, src: str, dst: str) -> None:
        raise NotImplementedError("Cloud storage coming soon")
