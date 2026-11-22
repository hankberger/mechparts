"""Rigid shaft coupler joining two shafts, with set screw or clamp fixing."""

from __future__ import annotations

import math
from typing import Literal

import build123d as bd
from pydantic import Field

from mechparts.core import checks, features
from mechparts.core.models import ParamIssue, Printability
from mechparts.core.part import PartFamily, PartParams, SetScrewSize, clearance, mm
from mechparts.core.standards import METRIC_SCREWS

SLOT_WIDTH = 1.0  # clamp slit width
CLAMP_MIN_JAW = 2.0  # material between slit and screw head seat on each side


class ShaftCouplerParams(PartParams):
    bore_a: float = mm(5.0, 1.0, 30.0, "Shaft diameter for the bottom half (clearance is added).")
    bore_b: float = mm(8.0, 1.0, 30.0, "Shaft diameter for the top half (clearance is added).")
    outer_diameter: float = mm(22.0, 5.0, 80.0, "Outside diameter of the coupler.")
    length: float = mm(25.0, 6.0, 120.0, "Overall length; each shaft gets half.")
    style: Literal["set_screw", "clamp"] = Field(
        "set_screw",
        description=(
            "set_screw: one radial grub screw per half. clamp: each half is slit and squeezed by a tangential "
            "screw, which grips better and does not mar the shaft."
        ),
    )
    screw_size: SetScrewSize = Field("M3", description="Metric screw size for the set screws or clamp screws.")
    clearance: float = clearance()


def _clamp_layout(p: ShaftCouplerParams) -> dict[str, float]:
    """Positions for clamp style: screw axis along X, offset +Y from the coupler axis."""
    screw = METRIC_SCREWS[p.screw_size]
    bore_r = (max(p.bore_a, p.bore_b) + p.clearance) / 2
    y = bore_r + screw.clearance_hole / 2 + 0.8
    head_r = (screw.head_diameter + 0.4) / 2
    ro = p.outer_diameter / 2
    # Head seat: the counterbore floor sits where the whole head circle is inside the outer cylinder.
    reach = ro * ro - (y + head_r) ** 2
    seat_x = math.sqrt(reach) - 0.5 if reach > 0 else 0.0
    need_ro = math.hypot(SLOT_WIDTH / 2 + CLAMP_MIN_JAW + 0.5, y + head_r)
    return {"y": y, "seat_x": seat_x, "head_r": head_r, "need_od": 2 * need_ro}


class ShaftCoupler(PartFamily):
    id = "shaft_coupler"
    name = "Rigid shaft coupler"
    summary = "Rigid coupler joining two shafts of equal or different diameters, set screw or clamp style."
    description = (
        "Cylindrical rigid coupler. Bore A occupies the bottom half and bore B the top half, along Z. "
        "Set screw style puts one radial tap-size hole in each half (along +Y). Clamp style slits each half "
        "along +Y and adds a tangential clearance hole, tap hole and counterbore so one screw squeezes each "
        "half; the two halves are separated by a transverse slit so they clamp independently."
    )
    tags = ["coupler", "shaft coupler", "rigid coupler", "coupling", "stepper", "lead screw", "clamp", "set screw"]
    standards = ["M2", "M2.5", "M3", "M4", "M5", "5 mm shaft", "8 mm shaft", "NEMA 17"]
    compatibility = [
        "bore_a and bore_b fit shafts of those diameters, e.g. 5 mm NEMA 17 motor shaft to 8 mm lead screw.",
        "Rigid couplers need well aligned shafts; for misalignment use a flexible coupler instead.",
        "Clamp style takes a socket head cap screw of screw_size; set screw style takes a grub screw.",
    ]
    printability = Printability(
        orientation="Standing on one end (Z up). No supports needed.",
        supports_needed=False,
        notes=[
            "Use at least 4 perimeters so screw threads and clamp jaws are solid plastic.",
            "Clamp style: the tangential holes bridge; a small droop is normal.",
        ],
    )
    Params = ShaftCouplerParams
    generator_version = "1"
    computed_dimensions = {
        "bore_a_actual_diameter": "Printed bore A including clearance.",
        "bore_b_actual_diameter": "Printed bore B including clearance.",
        "outer_diameter": "Outside diameter.",
        "length": "Overall length.",
        "clamp_screw_max_length": "Clamp style: longest screw that fits from head seat to far side (0 for set screw style).",
    }

    def computed(self, p: ShaftCouplerParams) -> dict[str, float]:
        out = {
            "bore_a_actual_diameter": round(p.bore_a + p.clearance, 4),
            "bore_b_actual_diameter": round(p.bore_b + p.clearance, 4),
            "outer_diameter": p.outer_diameter,
            "length": p.length,
            "clamp_screw_max_length": 0.0,
        }
        if p.style == "clamp":
            lay = _clamp_layout(p)
            ro = p.outer_diameter / 2
            far = math.sqrt(max(0.0, ro * ro - lay["y"] ** 2))
            out["clamp_screw_max_length"] = round(max(0.0, lay["seat_x"] + far - 0.5), 2)
        return out

    def check(self, p: ShaftCouplerParams) -> list[ParamIssue]:
        issues: list[ParamIssue] = []
        screw = METRIC_SCREWS[p.screw_size]
        bore = max(p.bore_a, p.bore_b) + p.clearance
        half = p.length / 2
        if p.style == "set_screw":
            need = bore + 2 * screw.nominal
            if p.outer_diameter < need:
                issues.append(
                    ParamIssue(
                        param="outer_diameter",
                        code="too_small",
                        message=(
                            f"outer_diameter {p.outer_diameter} mm leaves less than {screw.nominal} mm of wall around "
                            f"the {bore:.2f} mm bore for an {p.screw_size} set screw. Use outer_diameter >= {need:.2f} mm "
                            "or a smaller screw_size."
                        ),
                        allowed_min=round(need, 3),
                    )
                )
            need_len = 2 * (screw.tap_hole + 2 * 0.8)
        else:
            lay = _clamp_layout(p)
            if p.outer_diameter < lay["need_od"]:
                issues.append(
                    ParamIssue(
                        param="outer_diameter",
                        code="too_small",
                        message=(
                            f"outer_diameter {p.outer_diameter} mm has no room for an {p.screw_size} clamp screw and its "
                            f"head beside the {bore:.2f} mm bore. Use outer_diameter >= {lay['need_od']:.2f} mm or a "
                            "smaller screw_size."
                        ),
                        allowed_min=round(lay["need_od"], 3),
                    )
                )
            need_len = 2 * (screw.head_diameter + 2.0) + SLOT_WIDTH
        if p.length < need_len:
            issues.append(
                ParamIssue(
                    param="length",
                    code="too_small",
                    message=(
                        f"length {p.length} mm is too short for an {p.screw_size} screw in each half "
                        f"({half} mm per half). Use length >= {need_len:.2f} mm."
                    ),
                    allowed_min=round(need_len, 3),
                )
            )
        if p.outer_diameter - bore < 2 * checks.MIN_WALL:
            need = bore + 2 * checks.MIN_WALL
            if not any(i.param == "outer_diameter" for i in issues):
                issues.append(
                    ParamIssue(
                        param="outer_diameter",
                        code="too_small",
                        message=f"outer_diameter must exceed the largest bore by {2 * checks.MIN_WALL} mm (>= {need:.2f} mm).",
                        allowed_min=round(need, 3),
                    )
                )
        return issues

    def warnings(self, p: ShaftCouplerParams) -> list[str]:
        if p.style == "set_screw" and max(p.bore_a, p.bore_b) >= 8:
            return ["Set screws in plastic can slip on shafts of 8 mm or more; clamp style grips better."]
        return []

    def build(self, p: ShaftCouplerParams) -> bd.Part:
        half = p.length / 2
        bottom = {"align": (bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)}
        body = bd.Cylinder(p.outer_diameter / 2, p.length, **bottom)
        body = body - features.bore_cutter(p.bore_a + p.clearance, half + 1, -1)
        body = body - features.bore_cutter(p.bore_b + p.clearance, half + 1, half)
        screw = METRIC_SCREWS[p.screw_size]
        ro = p.outer_diameter / 2
        if p.style == "set_screw":
            for z in (half / 2, half + half / 2):
                body = body - features.radial_hole(screw.tap_hole, z, ro)
            return body
        lay = _clamp_layout(p)
        # Axial slit through the +Y wall, full length.
        slit = bd.Pos(0, ro, -1) * bd.Box(SLOT_WIDTH, 2 * ro, p.length + 2, **bottom)
        # Transverse slit between the halves, through the +Y side up to the axis.
        cross = bd.Pos(0, ro, half - SLOT_WIDTH / 2) * bd.Box(2 * ro + 2, 2 * ro, SLOT_WIDTH, **bottom)
        body = body - slit - cross
        for z in (half / 2, half + half / 2):
            # Clearance hole on +X side, tap hole on -X side, counterbore for the head on +X.
            clear = bd.Pos(0, lay["y"], z) * bd.Rot(0, 90, 0) * bd.Cylinder(
                screw.clearance_hole / 2, ro + 1, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)
            )
            tap = bd.Pos(0, lay["y"], z) * bd.Rot(0, -90, 0) * bd.Cylinder(
                screw.tap_hole / 2, ro + 1, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)
            )
            cbore = bd.Pos(lay["seat_x"], lay["y"], z) * bd.Rot(0, 90, 0) * bd.Cylinder(
                lay["head_r"], ro + 1, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)
            )
            body = body - clear - tap - cbore
        return body


PART = ShaftCoupler()
