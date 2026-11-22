"""Response and request models shared by the HTTP API and the MCP server."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

OutputFormat = Literal["stl", "step", "3mf"]
OUTPUT_LICENSE = "CC0-1.0"


class ParamIssue(BaseModel):
    """One problem with the supplied parameters, specific enough to act on."""

    param: str = Field(description="Parameter name the issue is about ('' if it concerns the request as a whole).")
    code: str = Field(description="Machine-readable issue code, e.g. 'too_large', 'missing', 'unknown_parameter'.")
    message: str = Field(description="Human/agent readable explanation including the fix.")
    allowed_min: float | None = Field(default=None, description="Smallest value that would be accepted, if known.")
    allowed_max: float | None = Field(default=None, description="Largest value that would be accepted, if known.")


class Printability(BaseModel):
    orientation: str = Field(description="Recommended print orientation.")
    supports_needed: bool = Field(description="Whether supports are needed in the recommended orientation.")
    notes: list[str] = Field(default_factory=list, description="Further printing advice.")
    clearance_param: str | None = Field(
        default="clearance", description="Name of the parameter that tunes fit tolerance for your printer."
    )


class PartSummary(BaseModel):
    id: str
    name: str
    summary: str
    tags: list[str]
    standards: list[str]
    license: str = OUTPUT_LICENSE


class PartDetail(PartSummary):
    description: str
    compatibility: list[str]
    printability: Printability
    generator_version: str
    units: str = "mm"
    formats: list[OutputFormat] = ["stl", "step", "3mf"]
    parameters_schema: dict[str, Any] = Field(description="JSON Schema for the parameters object.")
    computed_dimensions: dict[str, str] = Field(
        description="Key dimensions returned by generate_part, with their meaning."
    )


class ValidationResult(BaseModel):
    part_id: str
    valid: bool
    issues: list[ParamIssue] = Field(default_factory=list)
    resolved_params: dict[str, Any] | None = Field(
        default=None, description="Parameters with defaults filled in (present when the schema check passed)."
    )
    computed: dict[str, float] | None = Field(
        default=None, description="Key computed dimensions in mm (present when valid)."
    )
    warnings: list[str] = Field(default_factory=list)
    license: str = OUTPUT_LICENSE


class BoundingBox(BaseModel):
    min: list[float] = Field(description="[x, y, z] minimum corner in mm.")
    max: list[float] = Field(description="[x, y, z] maximum corner in mm.")
    size: list[float] = Field(description="[x, y, z] extents in mm.")


class GenerationResult(BaseModel):
    part_id: str
    format: OutputFormat
    hash: str = Field(description="Stable hash of (part_id, resolved params, generator version). Use with download.")
    file_sha256: str = Field(description="SHA-256 of the output file bytes.")
    size_bytes: int
    download_url: str
    file_path: str | None = Field(default=None, description="Local path of the file, when served from local storage.")
    resolved_params: dict[str, Any]
    computed: dict[str, float] = Field(description="Key computed dimensions in mm.")
    bounding_box: BoundingBox
    volume_mm3: float
    watertight: bool
    cached: bool = Field(description="True when the file was served from cache without regenerating.")
    generator_version: str
    units: str = "mm"
    warnings: list[str] = Field(default_factory=list)
    printability: Printability
    license: str = OUTPUT_LICENSE
