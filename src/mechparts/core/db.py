"""SQLite catalog of part families and metadata for generated files."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS parts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    summary TEXT NOT NULL,
    tags TEXT NOT NULL,
    standards TEXT NOT NULL,
    generator_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS geometries (
    hash TEXT PRIMARY KEY,
    part_id TEXT NOT NULL,
    generator_version TEXT NOT NULL,
    params TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS files (
    hash TEXT NOT NULL,
    format TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    result TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (hash, format)
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def sync_catalog(self, parts: list[dict[str, Any]]) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM parts")
            self._conn.executemany(
                "INSERT INTO parts (id, name, summary, tags, standards, generator_version) VALUES (?,?,?,?,?,?)",
                [
                    (p["id"], p["name"], p["summary"], json.dumps(p["tags"]), json.dumps(p["standards"]), p["version"])
                    for p in parts
                ],
            )
            self._conn.commit()

    def record_geometry(self, hash_: str, part_id: str, version: str, params: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO geometries (hash, part_id, generator_version, params, created_at) "
                "VALUES (?,?,?,?,?)",
                (hash_, part_id, version, json.dumps(params, sort_keys=True), time.time()),
            )
            self._conn.commit()

    def get_geometry(self, hash_: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM geometries WHERE hash = ?", (hash_,)).fetchone()
        if row is None:
            return None
        return {
            "hash": row["hash"],
            "part_id": row["part_id"],
            "generator_version": row["generator_version"],
            "params": json.loads(row["params"]),
        }

    def record_file(
        self, hash_: str, fmt: str, key: str, sha: str, size: int, result: dict[str, Any]
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO files (hash, format, storage_key, file_sha256, size_bytes, result, created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (hash_, fmt, key, sha, size, json.dumps(result), time.time()),
            )
            self._conn.commit()

    def get_file(self, hash_: str, fmt: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM files WHERE hash = ? AND format = ?", (hash_, fmt)
            ).fetchone()
        if row is None:
            return None
        return {
            "storage_key": row["storage_key"],
            "file_sha256": row["file_sha256"],
            "size_bytes": row["size_bytes"],
            "result": json.loads(row["result"]),
        }
