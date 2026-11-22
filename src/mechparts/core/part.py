"""Base class every part family derives from.

A part family is one module in ``mechparts.parts`` that defines a subclass of
``PartFamily`` and exposes an instance as the module-level name ``PART``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from mechparts.core.models import ParamIssue, Printability


class PartParams(BaseModel):
    """Base for parameter models. Unknown keys are rejected so typos surface."""

    model_config = ConfigDict(extra="forbid")


def mm(default: float, ge: float, le: float, description: str, **kw: Any) -> Any:
    """A length parameter in millimetres."""
    return Field(default, ge=ge, le=le, description=description, json_schema_extra={"units": "mm"}, **kw)


def deg(default: float, ge: float, le: float, description: str) -> Any:
    return Field(default, ge=ge, le=le, description=description, json_schema_extra={"units": "deg"})


def count(default: int, ge: int, le: int, description: str) -> Any:
    return Field(default, ge=ge, le=le, description=description, json_schema_extra={"units": "count"})


def clearance(default: float = 0.2, description: str | None = None) -> Any:
    return mm(
        default,
        0.0,
        1.0,
        description
        or "Diametral clearance added to bores and holes so they fit after printing; tune for your printer.",
    )


SetScrewSize = Literal["M2", "M2.5", "M3", "M4", "M5"]


class PartFamily(ABC):
    """Declarative description plus geometry function for one family of parts."""

    id: ClassVar[str]
    name: ClassVar[str]
    summary: ClassVar[str]
    description: ClassVar[str]
    tags: ClassVar[list[str]]
    standards: ClassVar[list[str]]
    compatibility: ClassVar[list[str]]
    printability: ClassVar[Printability]
    Params: ClassVar[type[PartParams]]
    #: Bump whenever geometry output changes for the same parameters. Part of the cache key.
    generator_version: ClassVar[str] = "1"
    #: Meaning of each key returned by ``computed``.
    computed_dimensions: ClassVar[dict[str, str]] = {}

    def check(self, p: Any) -> list[ParamIssue]:
        """Cross-parameter validation. Return an empty list when the combination is buildable."""
        return []

    def warnings(self, p: Any) -> list[str]:
        """Non-fatal advice about a valid parameter set."""
        return []

    def computed(self, p: Any) -> dict[str, float]:
        """Key derived dimensions in mm, for the response."""
        return {}

    @abstractmethod
    def build(self, p: Any) -> Any:
        """Return a build123d ``Part``/``Solid`` in mm, sitting on the XY plane."""

    def parameters_schema(self) -> dict[str, Any]:
        schema = self.Params.model_json_schema()
        schema.pop("title", None)
        for prop in schema.get("properties", {}).values():
            prop.pop("title", None)
        return schema
