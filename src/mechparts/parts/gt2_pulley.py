"""GT2 (2 mm pitch) timing pulley with optional flanges, hub and set screw."""

from __future__ import annotations

import math
from typing import Literal

import build123d as bd
from pydantic import Field

from mechparts.core import checks, features
from mechparts.core.models import ParamIssue, Printability
from mechparts.core.part import PartFamily, PartParams, SetScrewSize, clearance, count, mm
from mechparts.core.standards import METRIC_SCREWS

# GT2 2 mm belt geometry. Gates does not publish the exact pulley profile; these are the
# nominal belt figures used by common open-source pulley generators.
PITCH = 2.0
PITCH_LINE_OFFSET = 0.254  # belt pitch line sits this far outside the pulley OD
GROOVE_DEPTH = 0.75  # belt tooth height
GROOVE_BOTTOM_RADIUS = 0.555  # belt tooth tip radius
GROOVE_WIDTH_AT_OD = 1.40  # belt tooth base width plus running clearance
LAND_FILLET = 0.15
FLANGE_RISE = 2.0  # flange extends this far beyond the OD (belt is ~1.4 mm thick)
FLANGE_THICKNESS = 1.0
EDGE_MARGIN = 0.5  # extra toothed length on each side of the belt


class GT2PulleyParams(PartParams):
    teeth: int = count(20, 10, 150, "Number of teeth (grooves). Pitch diameter = teeth * 2 / pi.")
    belt_width: Literal[6, 10] = Field(6, description="GT2 belt width in mm: 6 or 10.", json_schema_extra={"units": "mm"})
    bore_diameter: float = mm(5.0, 0.0, 50.0, "Shaft diameter the bore fits (clearance is added). 0 for no bore.")
    bore_type: Literal["round", "d_shaft"] = Field("round", description="Round bore or D-shaft bore with one flat.")
    d_flat_depth: float = mm(0.5, 0.1, 5.0, "For d_shaft: depth of the shaft's flat, measured in from its round surface.")
    flanges: bool = Field(True, description="Add belt-retaining flanges on both sides of the teeth.")
    hub_diameter: float = mm(16.0, 0.0, 150.0, "Hub diameter. 0 for no hub (set hub_length too).")
    hub_length: float = mm(7.0, 0.0, 50.0, "Hub length below the teeth. 0 for no hub.")
    set_screw: bool = Field(True, description="Add a radial set screw hole (tap size) through the hub or pulley body.")
    set_screw_size: SetScrewSize = Field("M3", description="Metric set screw size for the set screw hole.")
    clearance: float = clearance()


def _dims(p: GT2PulleyParams) -> dict[str, float]:
    pd = p.teeth * PITCH / math.pi
    od = pd - 2 * PITCH_LINE_OFFSET
    root = od - 2 * GROOVE_DEPTH
    toothed = p.belt_width + 2 * EDGE_MARGIN
    has_hub = p.hub_diameter > 0 and p.hub_length > 0
    flange_len = (FLANGE_THICKNESS + FLANGE_RISE + 0.5) if p.flanges else 0.0
    return {
        "pitch_diameter": pd,
        "outer_diameter": od,
        "root_diameter": root,
        "flange_diameter": od + 2 * FLANGE_RISE if p.flanges else 0.0,
        "bore_actual_diameter": p.bore_diameter + p.clearance if p.bore_diameter > 0 else 0.0,
        "toothed_length": toothed,
        "total_length": (p.hub_length if has_hub else 0.0) + toothed + flange_len,
    }


class GT2Pulley(PartFamily):
    id = "gt2_pulley"
    name = "GT2 timing pulley"
    summary = "GT2 2 mm pitch timing pulley for 6 or 10 mm belts, with flanges, hub and set screw options."
    description = (
        "Parametric GT2 (2GT) timing pulley. Pitch diameter is teeth * 2 / pi and the outer diameter is "
        "0.508 mm smaller (belt pitch line offset). The groove shape follows the nominal GT2 belt tooth "
        "(0.75 mm deep, 0.555 mm tip radius); Gates does not publish an exact pulley profile, so this is "
        "the widely used open-source approximation. The pulley axis is Z with the hub at the bottom."
    )
    tags = ["pulley", "timing pulley", "gt2", "2gt", "belt", "3d printer", "set screw", "d-shaft"]
    standards = ["GT2", "2GT", "2 mm pitch", "6 mm belt", "10 mm belt", "M2", "M2.5", "M3", "M4", "M5"]
    compatibility = [
        "Mates with a GT2 (2 mm pitch) belt of matching width: belt_width 6 or 10 mm.",
        "Belt length for two pulleys at center distance C: 2C + pi*(D1+D2)/2 + (D1-D2)^2/(4C), using pitch diameters.",
        "Use bore_diameter 5 with bore_type d_shaft for NEMA 17 stepper shafts.",
        "Pairs with GT2 idlers built on 608, 625 or 688 bearings (see bearing_mount).",
    ]
    printability = Printability(
        orientation="Hub down on the bed (Z up). The top flange is chamfered 45 degrees so no supports are needed.",
        supports_needed=False,
        notes=[
            "Print with a 0.4 mm nozzle or smaller and 0.1 to 0.15 mm layers so grooves resolve.",
            "Below about 16 teeth the belt wraps tightly; expect more wear.",
        ],
    )
    Params = GT2PulleyParams
    generator_version = "1"
    computed_dimensions = {
        "pitch_diameter": "Belt pitch line diameter (teeth * 2 / pi). Use it for belt length and ratios.",
        "outer_diameter": "Outside diameter of the toothed section.",
        "root_diameter": "Diameter at the groove bottoms.",
        "flange_diameter": "Flange outside diameter (0 without flanges).",
        "bore_actual_diameter": "Printed bore diameter including clearance (0 if no bore).",
        "toothed_length": "Axial length of the toothed section (belt width + 1 mm).",
        "total_length": "Overall axial length including hub and flanges.",
    }

    def computed(self, p: GT2PulleyParams) -> dict[str, float]:
        return {k: round(v, 4) for k, v in _dims(p).items()}

    def check(self, p: GT2PulleyParams) -> list[ParamIssue]:
        d = _dims(p)
        bore = d["bore_actual_diameter"]
        issues: list[ParamIssue] = []
        max_bore = d["root_diameter"] - 2 * checks.MIN_WALL - p.clearance
        if p.bore_diameter > 0 and bore > d["root_diameter"] - 2 * checks.MIN_WALL:
            issues.append(
                ParamIssue(
                    param="bore_diameter",
                    code="too_large",
                    message=(
                        f"bore_diameter {p.bore_diameter} mm is too large for {p.teeth} teeth: groove root diameter is "
                        f"{d['root_diameter']:.3f} mm and {checks.MIN_WALL} mm of wall must remain. Use bore_diameter "
                        f"<= {max_bore:.2f} mm or more teeth."
                    ),
                    allowed_max=round(max(0.0, max_bore), 3),
                )
            )
        issues += checks.check_d_flat(p.bore_type, p.bore_diameter, p.d_flat_depth)
        issues += checks.check_hub(p.hub_diameter, p.hub_length, bore, 150.0, "the 150 mm limit")
        if p.set_screw:
            use_hub = p.hub_diameter > 0 and p.hub_length > 0
            issues += checks.check_set_screw(
                p.set_screw_size,
                p.bore_diameter,
                bore,
                p.hub_diameter if use_hub else d["root_diameter"],
                p.hub_length if use_hub else d["toothed_length"],
                where="hub" if use_hub else "pulley body (no hub)",
                outer_param="hub_diameter" if use_hub else None,
                length_param="hub_length" if use_hub else "belt_width",
            )
        return issues

    def warnings(self, p: GT2PulleyParams) -> list[str]:
        out = []
        if p.teeth < 16:
            out.append("Fewer than 16 teeth bends the belt tightly and shortens belt life.")
        if not p.flanges:
            out.append("Without flanges the belt can walk off; use flanges on at least one pulley or idler.")
        return out

    # Geometry -----------------------------------------------------------
    @staticmethod
    def _groove() -> bd.Face:
        """One groove in local coordinates: x tangential, y radial, y = 0 at the OD."""
        c = (0.0, -GROOVE_DEPTH + GROOVE_BOTTOM_RADIUS)
        r = GROOVE_BOTTOM_RADIUS
        top = GROOVE_WIDTH_AT_OD / 2
        # Tangent from (top, 0) to the bottom circle, on the outer side.
        dx, dy = top - c[0], 0.0 - c[1]
        dist = math.hypot(dx, dy)
        base = math.atan2(dy, dx)
        off = math.acos(r / dist)
        a = base - off
        tx, ty = c[0] + r * math.cos(a), c[1] + r * math.sin(a)
        if ty > c[1]:  # pick the lower tangent point so the flank flares outward
            a = base + off
            tx, ty = c[0] + r * math.cos(a), c[1] + r * math.sin(a)
        pts = [(-top, 1.0), (-top, 0.0), (-tx, ty), (tx, ty), (top, 0.0), (top, 1.0)]
        poly = bd.Polygon(*pts, align=None)
        circ = bd.Pos(*c) * bd.Circle(r)
        return (poly + circ).faces()[0]

    def _toothed_profile(self, p: GT2PulleyParams) -> bd.Sketch:
        od = _dims(p)["outer_diameter"]
        ro = od / 2
        groove = self._groove()
        cutters = [
            bd.Rot(0, 0, 360 * i / p.teeth) * (bd.Pos(0, ro) * groove) for i in range(p.teeth)
        ]
        profile = bd.Sketch() + bd.Circle(ro)
        profile = profile - cutters
        return bd.offset(bd.offset(profile, -LAND_FILLET), LAND_FILLET)

    def build(self, p: GT2PulleyParams) -> bd.Part:
        d = _dims(p)
        ro, rf = d["outer_diameter"] / 2, d["flange_diameter"] / 2
        has_hub = p.hub_diameter > 0 and p.hub_length > 0
        z = 0.0
        bottom = {"align": (bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)}
        solids: list[bd.Part] = []
        if has_hub:
            solids.append(bd.Cylinder(p.hub_diameter / 2, p.hub_length + 0.01, **bottom))
            z = p.hub_length
        if p.flanges:
            solids.append(bd.Pos(0, 0, z) * bd.Cylinder(rf, FLANGE_THICKNESS + 0.01, **bottom))
            z += FLANGE_THICKNESS
        teeth_z0 = z
        solids.append(bd.Pos(0, 0, z) * bd.extrude(self._toothed_profile(p), amount=d["toothed_length"]))
        z += d["toothed_length"]
        if p.flanges:
            cone = bd.Cone(ro - 0.01, rf, FLANGE_RISE, **bottom)
            solids.append(bd.Pos(0, 0, z - 0.01) * cone)
            solids.append(bd.Pos(0, 0, z + FLANGE_RISE - 0.02) * bd.Cylinder(rf, 0.52, **bottom))
            z += FLANGE_RISE + 0.5
        part = solids[0]
        for s in solids[1:]:
            part = part + s
        if p.bore_diameter > 0:
            bore = d["bore_actual_diameter"]
            flat = p.bore_diameter / 2 - p.d_flat_depth + p.clearance / 2 if p.bore_type == "d_shaft" else None
            part = part - features.bore_cutter(bore, z + 2, -1, flat)
            if p.set_screw:
                screw = METRIC_SCREWS[p.set_screw_size]
                if has_hub:
                    hz, outer = p.hub_length / 2, p.hub_diameter / 2
                else:
                    hz, outer = teeth_z0 + d["toothed_length"] / 2, ro
                part = part - features.radial_hole(screw.tap_hole, hz, outer)
        return part


PART = GT2Pulley()
