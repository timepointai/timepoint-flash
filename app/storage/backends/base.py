"""Abstract base class for storage backends."""

from __future__ import annotations

from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """Abstract storage backend for blob I/O.

    Implementations must handle writing files, text, binary data,
    deleting directories, and checking existence.
    """

    @abstractmethod
    async def write_file(self, path: str, data: bytes) -> None:
        """Write binary data to a file.

        Args:
            path: Full file path.
            data: Binary data to write.
        """

    @abstractmethod
    async def write_text(self, path: str, text: str) -> None:
        """Write text data to a file.

        Args:
            path: Full file path.
            text: Text content to write.
        """

    @abstractmethod
    async def delete_directory(self, path: str) -> None:
        """Delete a directory and all its contents.

        Args:
            path: Directory path to delete.
        """

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if a path exists.

        Args:
            path: Path to check.

        Returns:
            True if the path exists.
        """

    @abstractmethod
    async def move_directory(self, src: str, dst: str) -> None:
        """Move a directory from src to dst.

        Args:
            src: Source path.
            dst: Destination path.
        """
