"""Pillow block bearing mount for 608, 625 and 688 ball bearings."""

from __future__ import annotations

from typing import Literal

import build123d as bd
from pydantic import Field

from mechparts.core.models import ParamIssue, Printability
from mechparts.core.part import PartFamily, PartParams, clearance, mm
from mechparts.core.standards import BEARINGS, METRIC_SCREWS

LIP = 1.0  # axial thickness of the retaining shoulder behind the bearing
LIP_STEP = 1.5  # shoulder radial height (keeps clear of the inner ring)


class BearingMountParams(PartParams):
    bearing: Literal["608", "625", "688"] = Field("608", description="Ball bearing designation: 608, 625 or 688.")
    mounting_hole_size: Literal["M3", "M4", "M5"] = Field("M4", description="Metric screw size for the two base holes.")
    mounting_hole_spacing: float = mm(42.0, 10.0, 200.0, "Center-to-center distance of the two mounting holes.")
    base_thickness: float = mm(5.0, 2.0, 30.0, "Thickness of the base plate.")
    housing_wall: float = mm(3.0, 1.5, 15.0, "Radial wall thickness around the bearing seat.")
    bearing_clearance: float = mm(
        0.1, 0.0, 0.5, "Diametral clearance added to the bearing seat; small, so the bearing press fits."
    )
    clearance: float = clearance(description="Diametral clearance added to the mounting holes; tune for your printer.")


def _dims(p: BearingMountParams) -> dict[str, float]:
    b = BEARINGS[p.bearing]
    screw = METRIC_SCREWS[p.mounting_hole_size]
    seat = b.outer_diameter + p.bearing_clearance
    rh = seat / 2 + p.housing_wall
    width = max(b.width + LIP, screw.clearance_hole + p.clearance + 2 * 2.0)
    margin = screw.head_diameter / 2 + 2.0
    return {
        "seat_diameter": seat,
        "shoulder_diameter": seat - 2 * LIP_STEP,
        "shaft_height": rh,
        "housing_diameter": 2 * rh,
        "width": width,
        "base_length": p.mounting_hole_spacing + 2 * margin,
        "hole_diameter": screw.clearance_hole + p.clearance,
        "fits_shaft_diameter": b.bore,
    }


class BearingMount(PartFamily):
    id = "bearing_mount"
    name = "Pillow block bearing mount"
    summary = "Pillow block for 608, 625 or 688 ball bearings with two base mounting holes."
    description = (
        "Pillow block housing for a standard ball bearing. The base sits on the XY plane with the shaft axis "
        "along Y at shaft_height (equal to housing radius, so the housing bottom is flush with the base). "
        "The bearing presses into a seat open on the -Y face and stops against a 1 mm shoulder on +Y. Two "
        "clearance holes on the X axis at mounting_hole_spacing bolt it down."
    )
    tags = ["bearing", "bearing mount", "pillow block", "bearing block", "608", "625", "688", "shaft support", "idler"]
    standards = ["608", "625", "688", "608ZZ", "625ZZ", "688ZZ", "M3", "M4", "M5", "8 mm shaft", "5 mm shaft"]
    compatibility = [
        "bearing 608 (8x22x7) fits 8 mm shafts; 688 (8x16x5) fits 8 mm shafts; 625 (5x16x5) fits 5 mm shafts.",
        "Shaft axis height above the mounting surface is returned as shaft_height; match it when pairing two blocks.",
        "Mounting holes take mounting_hole_size socket head screws through the base.",
    ]
    printability = Printability(
        orientation=(
            "On its side with the shaft axis vertical and the shoulder (+Y face) on the bed: the bearing seat "
            "prints as a true circle and no supports are needed."
        ),
        supports_needed=False,
        notes=[
            "If the bearing is too tight, raise bearing_clearance in 0.05 mm steps; if loose, lower it.",
            "Mounting holes print horizontally in this orientation and bridge cleanly at these sizes.",
        ],
        clearance_param="bearing_clearance",
    )
    Params = BearingMountParams
    generator_version = "1"
    computed_dimensions = {
        "seat_diameter": "Bearing seat bore including bearing_clearance.",
        "shoulder_diameter": "Opening through the retaining shoulder.",
        "shaft_height": "Height of the shaft axis above the mounting surface.",
        "housing_diameter": "Outside diameter of the round housing.",
        "width": "Size along the shaft axis (Y).",
        "base_length": "Overall length of the base along X.",
        "hole_diameter": "Mounting hole diameter including clearance.",
        "fits_shaft_diameter": "Shaft diameter of the selected bearing.",
    }

    def computed(self, p: BearingMountParams) -> dict[str, float]:
        return {k: round(v, 4) for k, v in _dims(p).items()}

    def check(self, p: BearingMountParams) -> list[ParamIssue]:
        d = _dims(p)
        screw = METRIC_SCREWS[p.mounting_hole_size]
        issues: list[ParamIssue] = []
        min_spacing = d["housing_diameter"] + screw.head_diameter + 1.0
        if p.mounting_hole_spacing < min_spacing:
            issues.append(
                ParamIssue(
                    param="mounting_hole_spacing",
                    code="too_small",
                    message=(
                        f"mounting_hole_spacing {p.mounting_hole_spacing} mm puts the {p.mounting_hole_size} screw heads "
                        f"inside the {d['housing_diameter']:.2f} mm housing of a {p.bearing} mount. Use "
                        f"mounting_hole_spacing >= {min_spacing:.2f} mm."
                    ),
                    allowed_min=round(min_spacing, 3),
                )
            )
        if p.base_thickness > d["shaft_height"]:
            issues.append(
                ParamIssue(
                    param="base_thickness",
                    code="too_large",
                    message=(
                        f"base_thickness {p.base_thickness} mm is above the shaft axis ({d['shaft_height']:.2f} mm) "
                        f"and would cover the bearing. Use base_thickness <= {d['shaft_height']:.2f} mm."
                    ),
                    allowed_max=round(d["shaft_height"], 3),
                )
            )
        return issues

    def build(self, p: BearingMountParams) -> bd.Part:
        d = _dims(p)
        rh = d["shaft_height"]
        w = d["width"]
        bottom = {"align": (bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)}
        base = bd.Box(d["base_length"], w, p.base_thickness, **bottom)
        block = bd.Box(2 * rh, w, rh, **bottom)
        ring = bd.Pos(0, 0, rh) * bd.Rot(90, 0, 0) * bd.Cylinder(rh, w)
        part = base + block + ring
        # Bearing seat open on -Y, shoulder on +Y.
        y_minus = -w / 2
        seat_depth = w - LIP
        seat = bd.Pos(0, y_minus - 1, rh) * bd.Rot(-90, 0, 0) * bd.Cylinder(d["seat_diameter"] / 2, seat_depth + 1, **bottom)
        through = bd.Pos(0, y_minus - 1, rh) * bd.Rot(-90, 0, 0) * bd.Cylinder(d["shoulder_diameter"] / 2, w + 2, **bottom)
        part = part - seat - through
        for x in (-p.mounting_hole_spacing / 2, p.mounting_hole_spacing / 2):
            hole = bd.Pos(x, 0, -1) * bd.Cylinder(d["hole_diameter"] / 2, p.base_thickness + 2, **bottom)
            part = part - hole
        return part


PART = BearingMount()
