"""Stable request hashing for the generation cache."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def normalize(value: Any) -> Any:
    """Canonical form for hashing: floats rounded to 1 µm-ish precision, ints kept, keys sorted."""
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        r = round(value, 6)
        return int(r) if r.is_integer() else r
    if isinstance(value, dict):
        return {str(k): normalize(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [normalize(v) for v in value]
    raise TypeError(f"Cannot normalize {type(value).__name__}")


def geometry_hash(part_id: str, generator_version: str, params: dict[str, Any]) -> str:
    """Hash naming one geometry. The output format is not part of it; it picks a file for this hash."""
    payload = json.dumps(
        {"part": part_id, "version": generator_version, "params": normalize(params)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:32]
