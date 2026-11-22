"""Blob storage for generated files. Local filesystem now; S3 later behind the same interface."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol


class Storage(Protocol):
    def exists(self, key: str) -> bool: ...
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def local_path(self, key: str) -> str | None:
        """Filesystem path of the object, or None for remote backends."""
        ...


class LocalStorage:
    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if "/" in key or "\\" in key or key.startswith("."):
            raise ValueError(f"Invalid storage key {key!r}")
        # Shard by prefix so one directory never holds millions of files.
        return self.root / key[:2] / key

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def local_path(self, key: str) -> str | None:
        return str(self._path(key).resolve())
