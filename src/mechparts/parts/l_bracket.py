"""L-bracket (angle bracket) with clearance holes on both legs and optional gussets."""

from __future__ import annotations

import build123d as bd
from pydantic import Field

from mechparts.core.models import ParamIssue, Printability
from mechparts.core.part import PartFamily, PartParams, SetScrewSize, clearance, count, mm
from mechparts.core.standards import METRIC_SCREWS

GUSSET_FRACTION = 0.6  # gusset legs span this fraction of the shorter free leg


class LBracketParams(PartParams):
    leg_a: float = mm(30.0, 5.0, 200.0, "Length of the horizontal leg (along X), measured from the outside corner.")
    leg_b: float = mm(30.0, 5.0, 200.0, "Length of the vertical leg (along Z), measured from the outside corner.")
    width: float = mm(20.0, 5.0, 200.0, "Bracket width (along Y).")
    thickness: float = mm(4.0, 1.0, 20.0, "Thickness of both legs.")
    hole_size: SetScrewSize = Field("M3", description="Metric screw size for the clearance holes.")
    holes_per_leg: int = count(2, 0, 10, "Number of clearance holes in each leg, evenly spaced along the leg.")
    gusset: bool = Field(False, description="Add triangular gussets at both side edges to stiffen the corner.")
    gusset_thickness: float = mm(3.0, 1.0, 20.0, "Thickness of each gusset (used when gusset is true).")
    clearance: float = clearance(description="Diametral clearance added to the screw holes; tune for your printer.")


def _layout(p: LBracketParams) -> dict[str, float]:
    s = METRIC_SCREWS[p.hole_size]
    n = max(p.holes_per_leg, 1)
    free_a, free_b = p.leg_a - p.thickness, p.leg_b - p.thickness
    return {
        "hole_diameter": s.clearance_hole + p.clearance if p.holes_per_leg else 0.0,
        "hole_spacing_a": free_a / n if p.holes_per_leg > 1 else 0.0,
        "hole_spacing_b": free_b / n if p.holes_per_leg > 1 else 0.0,
        "first_hole_a": p.thickness + free_a / (2 * n) if p.holes_per_leg else 0.0,
        "first_hole_b": p.thickness + free_b / (2 * n) if p.holes_per_leg else 0.0,
        "gusset_size": GUSSET_FRACTION * min(free_a, free_b) if p.gusset else 0.0,
    }


class LBracket(PartFamily):
    id = "l_bracket"
    name = "L-bracket"
    summary = "Right-angle L-bracket with evenly spaced screw holes on both legs and optional gussets."
    description = (
        "90 degree angle bracket. Leg A lies on the XY plane along +X, leg B rises along +Z, both from the "
        "outside corner at the origin, and the bracket is centered on Y. Clearance holes are centered across "
        "the width and evenly spaced along the free length of each leg (beyond the other leg's thickness). "
        "Optional gussets sit flush with both side faces."
    )
    tags = ["bracket", "l-bracket", "angle bracket", "corner bracket", "mounting", "gusset", "frame"]
    standards = ["M2", "M2.5", "M3", "M4", "M5", "2020 extrusion", "ISO 273"]
    compatibility = [
        "hole_size M5 with width 20 suits 2020 aluminium extrusion (use M5 T-nuts).",
        "Holes are clearance holes for hole_size screws; the computed first_hole_a/b and hole_spacing_a/b give positions.",
    ]
    printability = Printability(
        orientation="Leg A flat on the bed, leg B vertical. Holes in leg B print horizontally and bridge; no supports.",
        supports_needed=False,
        notes=["For load-bearing use, add gussets and print with 4 or more perimeters."],
    )
    Params = LBracketParams
    generator_version = "1"
    computed_dimensions = {
        "hole_diameter": "Clearance hole diameter including clearance (0 without holes).",
        "hole_spacing_a": "Center-to-center hole spacing on leg A (0 for fewer than two holes).",
        "hole_spacing_b": "Center-to-center hole spacing on leg B (0 for fewer than two holes).",
        "first_hole_a": "Distance from the outside corner to the first hole center on leg A.",
        "first_hole_b": "Distance from the outside corner to the first hole center on leg B.",
        "gusset_size": "Length of each gusset's legs (0 without gussets).",
    }

    def computed(self, p: LBracketParams) -> dict[str, float]:
        return {k: round(v, 4) for k, v in _layout(p).items()}

    def check(self, p: LBracketParams) -> list[ParamIssue]:
        issues: list[ParamIssue] = []
        s = METRIC_SCREWS[p.hole_size]
        for leg in ("leg_a", "leg_b"):
            if getattr(p, leg) < p.thickness + 1.0:
                issues.append(
                    ParamIssue(
                        param=leg,
                        code="too_small",
                        message=f"{leg} must exceed thickness by at least 1 mm (>= {p.thickness + 1:.2f} mm).",
                        allowed_min=round(p.thickness + 1.0, 3),
                    )
                )
        if p.holes_per_leg:
            pitch_needed = s.head_diameter + 0.5
            for leg in ("leg_a", "leg_b"):
                need = p.thickness + p.holes_per_leg * pitch_needed
                if getattr(p, leg) < need:
                    issues.append(
                        ParamIssue(
                            param=leg,
                            code="too_small",
                            message=(
                                f"{leg} {getattr(p, leg)} mm is too short for {p.holes_per_leg} {p.hole_size} holes "
                                f"(each needs {pitch_needed:.1f} mm for the screw head). Use {leg} >= {need:.2f} mm "
                                "or fewer holes_per_leg."
                            ),
                            allowed_min=round(need, 3),
                        )
                    )
            need_w = s.head_diameter + 1.0 + (2 * p.gusset_thickness if p.gusset else 0.0)
            if p.width < need_w:
                issues.append(
                    ParamIssue(
                        param="width",
                        code="too_small",
                        message=(
                            f"width {p.width} mm is too narrow for {p.hole_size} screw heads"
                            + (" between the gussets" if p.gusset else "")
                            + f". Use width >= {need_w:.2f} mm."
                        ),
                        allowed_min=round(need_w, 3),
                    )
                )
        if p.gusset and 2 * p.gusset_thickness > p.width:
            issues.append(
                ParamIssue(
                    param="gusset_thickness",
                    code="too_large",
                    message=f"Two gussets of {p.gusset_thickness} mm do not fit in width {p.width} mm.",
                    allowed_max=round(p.width / 2, 3),
                )
            )
        return issues

    def build(self, p: LBracketParams) -> bd.Part:
        lay = _layout(p)
        t, w = p.thickness, p.width
        leg_a = bd.Box(p.leg_a, w, t, align=(bd.Align.MIN, bd.Align.CENTER, bd.Align.MIN))
        leg_b = bd.Box(t, w, p.leg_b, align=(bd.Align.MIN, bd.Align.CENTER, bd.Align.MIN))
        part = leg_a + leg_b
        if p.gusset:
            g = lay["gusset_size"]
            tri = bd.Polygon((t - 0.01, t - 0.01), (t + g, t - 0.01), (t - 0.01, t + g), align=None)
            # Plane.XZ maps sketch (x, y) to (X, Z) and extrudes toward -Y, so offset to each side face.
            for y0 in (w / 2, -w / 2 + p.gusset_thickness):
                face = bd.Plane.XZ.offset(-y0) * tri
                part = part + bd.extrude(face, amount=p.gusset_thickness)
        n = p.holes_per_leg
        if n:
            r = lay["hole_diameter"] / 2
            step_a = (p.leg_a - t) / n
            step_b = (p.leg_b - t) / n
            for i in range(n):
                x = t + (i + 0.5) * step_a
                part = part - bd.Pos(x, 0, -1) * bd.Cylinder(r, t + 2, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
                z = t + (i + 0.5) * step_b
                part = part - bd.Pos(-1, 0, z) * bd.Rot(0, 90, 0) * bd.Cylinder(
                    r, t + 2, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)
                )
        return part


PART = LBracket()
