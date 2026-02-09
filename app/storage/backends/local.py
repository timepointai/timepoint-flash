"""Local filesystem storage backend using pathlib."""

from __future__ import annotations

import shutil
from pathlib import Path

from app.storage.backends.base import StorageBackend


class LocalStorageBackend(StorageBackend):
    """Pathlib-based local filesystem storage backend."""

    async def write_file(self, path: str, data: bytes) -> None:
        """Write binary data to a local file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    async def write_text(self, path: str, text: str) -> None:
        """Write text data to a local file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    async def delete_directory(self, path: str) -> None:
        """Delete a local directory and all contents."""
        p = Path(path)
        if p.exists():
            shutil.rmtree(p)

    async def exists(self, path: str) -> bool:
        """Check if a local path exists."""
        return Path(path).exists()

    async def move_directory(self, src: str, dst: str) -> None:
        """Move a directory from src to dst."""
        dst_path = Path(dst)
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src, dst)
