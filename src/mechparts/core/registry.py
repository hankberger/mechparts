"""Discovers part families: every module in ``mechparts.parts`` exposing ``PART``."""

from __future__ import annotations

import importlib
import pkgutil
from functools import lru_cache

import mechparts.parts
from mechparts.core.part import PartFamily


@lru_cache(maxsize=1)
def all_parts() -> dict[str, PartFamily]:
    found: dict[str, PartFamily] = {}
    for info in sorted(pkgutil.iter_modules(mechparts.parts.__path__), key=lambda m: m.name):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{mechparts.parts.__name__}.{info.name}")
        part = getattr(module, "PART", None)
        if part is None:
            continue
        if not isinstance(part, PartFamily):
            raise TypeError(f"{module.__name__}.PART must be a PartFamily instance")
        if part.id in found:
            raise ValueError(f"Duplicate part id {part.id!r} in {module.__name__}")
        found[part.id] = part
    return found


def get(part_id: str) -> PartFamily | None:
    return all_parts().get(part_id)
