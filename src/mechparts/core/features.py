"""Reusable geometry features shared by part families (bores, set screws)."""

from __future__ import annotations

import math

import build123d as bd


def bore_cutter(diameter: float, length: float, z0: float, d_flat_from_center: float | None = None) -> bd.Part:
    """Through-bore along Z from z0 to z0 + length. With ``d_flat_from_center`` it is a D-bore
    whose flat faces +Y at that distance from the axis (set screws also enter from +Y)."""
    cyl = bd.Pos(0, 0, z0) * bd.Cylinder(diameter / 2, length, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    if d_flat_from_center is None:
        return cyl
    cut = bd.Pos(0, d_flat_from_center + diameter, z0) * bd.Box(
        diameter * 2, diameter * 2, length, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)
    )
    return cyl - cut


def radial_hole(diameter: float, z: float, outer_radius: float, inner_radius: float = 0.0) -> bd.Part:
    """Hole along +Y at height z, from inner_radius out past outer_radius."""
    length = outer_radius - inner_radius + 2.0
    hole = bd.Cylinder(diameter / 2, length, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    return bd.Pos(0, inner_radius - 1.0, z) * bd.Rot(-90, 0, 0) * hole


def polar_point(r: float, angle: float) -> tuple[float, float]:
    return (r * math.cos(angle), r * math.sin(angle))
