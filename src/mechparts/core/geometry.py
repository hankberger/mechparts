"""Shape analysis, deterministic export and mesh quality checks."""

from __future__ import annotations

import io
import os
import re
import tempfile
import uuid
import zipfile
from dataclasses import dataclass

import build123d as bd
import trimesh

from mechparts.core.models import BoundingBox, OutputFormat

# Mesh resolution for STL/3MF. 0.01 mm chord error is far below FDM resolution
# while keeping files reasonably small.
LINEAR_TOLERANCE = 0.01
ANGULAR_TOLERANCE = 0.5  # radians; chord error (LINEAR_TOLERANCE) is what governs accuracy
STEP_TIMESTAMP = "2000-01-01T00:00:00"


class GeometryError(RuntimeError):
    """Raised when generated geometry fails a quality check."""


@dataclass
class ShapeInfo:
    bounding_box: BoundingBox
    volume_mm3: float


def _r(v: float) -> float:
    return round(float(v), 4) + 0.0  # + 0.0 turns -0.0 into 0.0


def analyze(shape: bd.Shape) -> ShapeInfo:
    solids = shape.solids()
    if len(solids) != 1:
        raise GeometryError(f"Generated shape has {len(solids)} solids; expected exactly one connected solid.")
    if not shape.is_valid:
        raise GeometryError("Generated B-rep is not valid.")
    bb = shape.bounding_box()
    box = BoundingBox(
        min=[_r(bb.min.X), _r(bb.min.Y), _r(bb.min.Z)],
        max=[_r(bb.max.X), _r(bb.max.Y), _r(bb.max.Z)],
        size=[_r(bb.size.X), _r(bb.size.Y), _r(bb.size.Z)],
    )
    volume = shape.volume
    if volume <= 0:
        raise GeometryError("Generated solid has non-positive volume.")
    return ShapeInfo(bounding_box=box, volume_mm3=round(volume, 3))


def _via_tempfile(write, suffix: str) -> bytes:
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        write(path)
        with open(path, "rb") as f:
            return f.read()
    finally:
        os.unlink(path)


def export_bytes(shape: bd.Shape, fmt: OutputFormat, seed: str) -> bytes:
    """Export ``shape`` to ``fmt``. Output is byte-for-byte reproducible for a given seed."""
    if fmt == "stl":
        return _via_tempfile(
            lambda p: bd.export_stl(shape, p, tolerance=LINEAR_TOLERANCE, angular_tolerance=ANGULAR_TOLERANCE),
            ".stl",
        )
    if fmt == "step":
        buf = io.BytesIO()
        bd.export_step(shape, buf, timestamp=STEP_TIMESTAMP)
        return buf.getvalue()
    if fmt == "3mf":

        def write(p: str) -> None:
            mesher = bd.Mesher()
            mesher.add_shape(
                shape,
                linear_deflection=LINEAR_TOLERANCE,
                angular_deflection=ANGULAR_TOLERANCE,
                uuid_value=uuid.uuid5(uuid.NAMESPACE_URL, f"mechparts:{seed}"),
            )
            mesher.write(p)

        return _deterministic_3mf(_via_tempfile(write, ".3mf"), seed)
    raise ValueError(f"Unsupported format {fmt!r}")


_UUID_RE = re.compile(rb"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def _deterministic_3mf(data: bytes, seed: str) -> bytes:
    """lib3mf stamps random UUIDs on build items; replace them with seed-derived ones."""
    mapping: dict[bytes, bytes] = {}

    def sub(m: re.Match[bytes]) -> bytes:
        key = m.group(0).lower()
        if key not in mapping:
            mapping[key] = str(uuid.uuid5(uuid.NAMESPACE_URL, f"mechparts:{seed}:{len(mapping)}")).encode()
        return mapping[key]

    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in sorted(src.infolist(), key=lambda i: i.filename):
            body = src.read(info.filename)
            if info.filename.endswith((".model", ".rels", ".xml")):
                body = _UUID_RE.sub(sub, body)
            dst.writestr(zipfile.ZipInfo(info.filename, date_time=(1980, 1, 1, 0, 0, 0)), body, zipfile.ZIP_DEFLATED)
    return out.getvalue()


def check_mesh(stl_bytes: bytes) -> trimesh.Trimesh:
    """Load an STL and fail loudly unless it is a closed, consistently wound, manifold volume."""
    mesh = trimesh.load(io.BytesIO(stl_bytes), file_type="stl", force="mesh")
    problems = []
    if not mesh.is_watertight:
        problems.append("not watertight")
    if not mesh.is_winding_consistent:
        problems.append("inconsistent winding")
    if not mesh.is_volume:
        problems.append("not a valid volume")
    if problems:
        raise GeometryError("Generated mesh failed quality check: " + ", ".join(problems))
    return mesh
