"""Runtime settings, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("MECHPARTS_DATA_DIR", "data")))
    base_url: str = field(
        default_factory=lambda: os.environ.get("MECHPARTS_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    )

    #: Worker processes for geometry generation; 0 runs inline (no timeout).
    workers: int = field(default_factory=lambda: int(os.environ.get("MECHPARTS_WORKERS", "2")))
    #: Seconds a single generation may take before it is killed.
    timeout: float = field(default_factory=lambda: float(os.environ.get("MECHPARTS_TIMEOUT", "120")))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "mechparts.sqlite3"

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"
