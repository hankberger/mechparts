"""Involute spur gear with optional hub, set screw and D-shaft bore."""

from __future__ import annotations

import math

import build123d as bd
from pydantic import Field

from mechparts.core import features
from mechparts.core.involute import SpurGearGeometry
from mechparts.core.models import ParamIssue, Printability
from mechparts.core.part import PartFamily, PartParams, SetScrewSize, clearance, count, deg, mm
from mechparts.core.standards import METRIC_SCREWS
from typing import Literal

MIN_WALL = 1.0  # mm of material required between features


class SpurGearParams(PartParams):
    module: float = mm(1.0, 0.3, 10.0, "Gear module = pitch diameter / tooth count. Meshing gears must share it.")
    teeth: int = count(20, 6, 300, "Number of teeth.")
    pressure_angle: float = deg(20.0, 14.5, 30.0, "Pressure angle of the involute. Meshing gears must share it.")
    face_width: float = mm(6.0, 1.0, 100.0, "Axial thickness of the toothed section.")
    bore_diameter: float = mm(5.0, 0.0, 200.0, "Shaft diameter the bore fits (clearance is added). 0 for no bore.")
    bore_type: Literal["round", "d_shaft"] = Field("round", description="Round bore or D-shaft bore with one flat.")
    d_flat_depth: float = mm(
        0.5, 0.1, 5.0, "For d_shaft: depth of the shaft's flat, measured in from its round surface."
    )
    hub_diameter: float = mm(0.0, 0.0, 300.0, "Hub diameter. 0 for no hub (set hub_length too).")
    hub_length: float = mm(0.0, 0.0, 100.0, "Hub length beyond the gear face. 0 for no hub.")
    set_screw: bool = Field(False, description="Add a radial set screw hole (tap size) through the hub or gear body.")
    set_screw_size: SetScrewSize = Field("M3", description="Metric set screw size for the set screw hole.")
    clearance: float = clearance()


class SpurGear(PartFamily):
    id = "spur_gear"
    name = "Spur gear"
    summary = "Involute spur gear (ISO 53 rack profile) with optional hub, set screw and D-shaft bore."
    description = (
        "Parametric external spur gear. Tooth flanks are exact involutes generated from the ISO 53 "
        "basic rack (addendum 1.0 m, dedendum 1.25 m), including the root trochoid and natural undercut "
        "for low tooth counts, so it meshes with any standard gear of the same module and pressure angle. "
        "The gear lies on the XY plane with its axis along Z; the hub, if any, extends in +Z."
    )
    tags = ["gear", "spur gear", "involute", "transmission", "pinion", "set screw", "d-shaft"]
    standards = [
        "ISO 53",
        "module 0.5",
        "module 0.8",
        "module 1",
        "module 1.25",
        "module 1.5",
        "module 2",
        "module 2.5",
        "module 3",
        "M2",
        "M2.5",
        "M3",
        "M4",
        "M5",
    ]
    compatibility = [
        "Meshes with any spur gear of equal module and pressure_angle.",
        "Center distance for two meshing gears = module * (teeth_a + teeth_b) / 2.",
        "bore_diameter fits a shaft of that size; use bore_type d_shaft for D-cut motor shafts (e.g. 5 mm NEMA 17).",
        "set_screw_size M3 takes an M3 grub screw, which cuts its own thread in the tap-size hole.",
    ]
    printability = Printability(
        orientation="Flat on the gear face (Z up), hub pointing up.",
        supports_needed=False,
        notes=[
            "Module below about 0.8 is at the limit of FDM nozzle resolution; prefer resin or a 0.25 mm nozzle.",
            "If mating gears bind, add a little backlash by printing with slight negative XY compensation.",
        ],
    )
    generator_version = "1"
    computed_dimensions = {
        "pitch_diameter": "Diameter of the pitch circle (module * teeth).",
        "outer_diameter": "Tip (addendum) diameter, the largest diameter of the gear.",
        "root_diameter": "Root (dedendum) diameter.",
        "base_diameter": "Base circle diameter of the involute.",
        "circular_pitch": "Tooth spacing along the pitch circle (pi * module).",
        "bore_actual_diameter": "Printed bore diameter including clearance (0 if no bore).",
        "total_length": "Overall axial length including hub.",
    }

    def _geo(self, p: SpurGearParams) -> SpurGearGeometry:
        return SpurGearGeometry(p.module, p.teeth, p.pressure_angle)

    def computed(self, p: SpurGearParams) -> dict[str, float]:
        g = self._geo(p)
        return {
            "pitch_diameter": round(2 * g.pitch_radius, 4),
            "outer_diameter": round(2 * g.tip_radius, 4),
            "root_diameter": round(2 * g.root_radius, 4),
            "base_diameter": round(2 * g.base_radius, 4),
            "circular_pitch": round(g.circular_pitch, 4),
            "bore_actual_diameter": round(p.bore_diameter + p.clearance if p.bore_diameter > 0 else 0.0, 4),
            "total_length": round(p.face_width + (p.hub_length if p.hub_diameter > 0 else 0.0), 4),
        }

    def check(self, p: SpurGearParams) -> list[ParamIssue]:
        g = self._geo(p)
        issues: list[ParamIssue] = []
        root_d = 2 * g.root_radius

        if g.root_radius <= 0:
            issues.append(ParamIssue(param="teeth", code="too_small", message="Root diameter is not positive; increase teeth."))
            return issues

        tip_land = g.tip_half_angle() * 2 * g.tip_radius
        if tip_land < 0.1 * p.module:
            issues.append(
                ParamIssue(
                    param="teeth",
                    code="pointed_teeth",
                    message=(
                        f"With {p.teeth} teeth at {p.pressure_angle} deg pressure angle the teeth come to a point "
                        f"(tip land {tip_land:.3f} mm). Increase teeth or lower pressure_angle."
                    ),
                )
            )

        bore = p.bore_diameter + p.clearance if p.bore_diameter > 0 else 0.0
        max_bore = root_d - 2 * MIN_WALL - p.clearance
        if p.bore_diameter > 0 and bore > root_d - 2 * MIN_WALL:
            issues.append(
                ParamIssue(
                    param="bore_diameter",
                    code="too_large",
                    message=(
                        f"bore_diameter {p.bore_diameter} mm is too large: root diameter is {root_d:.3f} mm "
                        f"(module {p.module}, {p.teeth} teeth) and the bore plus {p.clearance} mm clearance must "
                        f"leave {MIN_WALL} mm of material. Use bore_diameter <= {max_bore:.2f} mm or more teeth."
                    ),
                    allowed_max=round(max(0.0, max_bore), 3),
                )
            )

        if p.bore_type == "d_shaft":
            if p.bore_diameter <= 0:
                issues.append(
                    ParamIssue(param="bore_type", code="requires_bore", message="bore_type d_shaft needs bore_diameter > 0.")
                )
            elif p.d_flat_depth >= p.bore_diameter / 2:
                issues.append(
                    ParamIssue(
                        param="d_flat_depth",
                        code="too_large",
                        message=f"d_flat_depth must be less than half of bore_diameter ({p.bore_diameter / 2} mm).",
                        allowed_max=round(p.bore_diameter / 2 - 0.01, 3),
                    )
                )

        has_hub = p.hub_diameter > 0 or p.hub_length > 0
        if has_hub:
            if p.hub_diameter <= 0 or p.hub_length <= 0:
                missing = "hub_diameter" if p.hub_diameter <= 0 else "hub_length"
                issues.append(
                    ParamIssue(
                        param=missing,
                        code="missing",
                        message="A hub needs both hub_diameter and hub_length > 0 (set both to 0 for no hub).",
                    )
                )
            else:
                min_hub = bore + 2 * MIN_WALL if bore > 0 else 2 * MIN_WALL
                if p.hub_diameter < min_hub:
                    issues.append(
                        ParamIssue(
                            param="hub_diameter",
                            code="too_small",
                            message=(
                                f"hub_diameter {p.hub_diameter} mm leaves less than {MIN_WALL} mm of wall around "
                                f"the {bore:.2f} mm bore. Use hub_diameter >= {min_hub:.2f} mm."
                            ),
                            allowed_min=round(min_hub, 3),
                        )
                    )
                if p.hub_diameter > root_d:
                    issues.append(
                        ParamIssue(
                            param="hub_diameter",
                            code="too_large",
                            message=(
                                f"hub_diameter {p.hub_diameter} mm exceeds the root diameter {root_d:.3f} mm and "
                                f"would collide with mating teeth. Use hub_diameter <= {root_d:.3f} mm."
                            ),
                            allowed_max=round(root_d, 3),
                        )
                    )

        if p.set_screw:
            screw = METRIC_SCREWS[p.set_screw_size]
            if p.bore_diameter <= 0:
                issues.append(
                    ParamIssue(param="set_screw", code="requires_bore", message="set_screw needs bore_diameter > 0.")
                )
            else:
                use_hub = p.hub_diameter > 0 and p.hub_length > 0
                outer = p.hub_diameter if use_hub else root_d
                length = p.hub_length if use_hub else p.face_width
                where = "hub" if use_hub else "gear body (no hub)"
                wall = (outer - bore) / 2
                if wall < screw.nominal:
                    need = bore + 2 * screw.nominal
                    issues.append(
                        ParamIssue(
                            param="hub_diameter" if use_hub else "set_screw",
                            code="too_small",
                            message=(
                                f"The {where} wall is {wall:.2f} mm, too thin for an {screw.size} set screw "
                                f"(needs {screw.nominal} mm of thread). "
                                + (f"Use hub_diameter >= {need:.2f} mm" if use_hub else "Add a hub")
                                + " or a smaller set_screw_size."
                            ),
                            allowed_min=round(need, 3) if use_hub else None,
                        )
                    )
                need_len = screw.tap_hole + 2 * 0.8
                if length < need_len:
                    issues.append(
                        ParamIssue(
                            param="hub_length" if use_hub else "face_width",
                            code="too_small",
                            message=(
                                f"The {where} is {length} mm long; an {screw.size} set screw hole needs at least "
                                f"{need_len:.2f} mm."
                            ),
                            allowed_min=round(need_len, 3),
                        )
                    )
        return issues

    def warnings(self, p: SpurGearParams) -> list[str]:
        g = self._geo(p)
        out = []
        if g.undercut:
            out.append(
                f"{p.teeth} teeth at {p.pressure_angle} deg are undercut, as on a hobbed gear. The gear meshes "
                "correctly but tooth roots are weaker; use more teeth for heavy loads."
            )
        if p.module < 0.8:
            out.append("Module below 0.8 mm is at the limit of FDM printing; consider resin or a smaller nozzle.")
        return out

    # Geometry -----------------------------------------------------------
    def _outline(self, g: SpurGearGeometry) -> bd.Wire:
        samples = 12
        rj = g.junction_radius()
        rr, ra = g.root_radius, g.tip_radius
        troch = [rr + (rj - rr) * (i / samples) ** 1.5 for i in range(samples + 1)]
        invo = [rj + (ra - rj) * i / samples for i in range(samples + 1)]

        def pts(radii, sign):
            return [features.polar_point(r, sign * g.half_angle(r) if r != rj else sign * g.involute_half_angle(r)) for r in radii]

        # One tooth centred on +X, traversed counter-clockwise.
        lower_t = pts(troch, -1)
        lower_i = pts(invo, -1)
        upper_i = list(reversed(pts(invo, 1)))
        upper_t = list(reversed(pts(troch, 1)))
        tip_a = g.half_angle(ra)
        root_a = g.trochoid_half_angle(rr)
        pitch = 2 * math.pi / g.teeth
        edges: list[bd.Edge] = [
            bd.Edge.make_spline([bd.Vector(*q) for q in lower_t]),
            bd.Edge.make_spline([bd.Vector(*q) for q in lower_i]),
            bd.Edge.make_three_point_arc(
                bd.Vector(*features.polar_point(ra, -tip_a)),
                bd.Vector(ra, 0),
                bd.Vector(*features.polar_point(ra, tip_a)),
            ),
            bd.Edge.make_spline([bd.Vector(*q) for q in upper_i]),
            bd.Edge.make_spline([bd.Vector(*q) for q in upper_t]),
        ]
        if pitch - 2 * root_a > 1e-6:
            edges.append(
                bd.Edge.make_three_point_arc(
                    bd.Vector(*features.polar_point(rr, root_a)),
                    bd.Vector(*features.polar_point(rr, pitch / 2)),
                    bd.Vector(*features.polar_point(rr, pitch - root_a)),
                )
            )
        all_edges: list[bd.Edge] = []
        for i in range(g.teeth):
            rot = bd.Rot(0, 0, math.degrees(i * pitch))
            all_edges.extend(rot * e for e in edges)
        return bd.Wire(all_edges)

    def build(self, p: SpurGearParams) -> bd.Part:
        g = self._geo(p)
        face = bd.Face(self._outline(g))
        gear = bd.extrude(face, amount=p.face_width)
        total = p.face_width
        has_hub = p.hub_diameter > 0 and p.hub_length > 0
        if has_hub:
            hub = bd.Pos(0, 0, p.face_width) * bd.Cylinder(
                p.hub_diameter / 2, p.hub_length, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)
            )
            gear = gear + hub
            total += p.hub_length
        if p.bore_diameter > 0:
            bore = p.bore_diameter + p.clearance
            flat = None
            if p.bore_type == "d_shaft":
                flat = p.bore_diameter / 2 - p.d_flat_depth + p.clearance / 2
            gear = gear - features.bore_cutter(bore, total + 2, -1, flat)
            if p.set_screw:
                screw = METRIC_SCREWS[p.set_screw_size]
                if has_hub:
                    z, outer = p.face_width + p.hub_length / 2, p.hub_diameter / 2
                else:
                    z, outer = p.face_width / 2, g.tip_radius
                gear = gear - features.radial_hole(screw.tap_hole, z, outer)
        return gear


PART = SpurGear()
