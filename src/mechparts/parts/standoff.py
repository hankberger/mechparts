"""Hex or round standoff / spacer for M2 to M5 screws, with male or female ends."""

from __future__ import annotations

import logging
import math
from typing import Literal

import build123d as bd
from pydantic import Field

from mechparts.core.models import ParamIssue, Printability
from mechparts.core.part import PartFamily, PartParams, SetScrewSize, clearance, mm
from mechparts.core.standards import METRIC_SCREWS

MIN_WALL = 0.8


class StandoffParams(PartParams):
    length: float = mm(10.0, 2.0, 100.0, "Body length, not counting any male stud.")
    body_shape: Literal["hex", "round"] = Field("hex", description="Hexagonal or round body.")
    body_size: float = mm(5.5, 3.0, 30.0, "Across flats for a hex body, outer diameter for a round body.")
    thread_size: SetScrewSize = Field("M3", description="Metric thread size the standoff is for: M2, M2.5, M3, M4 or M5.")
    ends: Literal["female_female", "male_female", "male_male"] = Field(
        "female_female", description="Which ends are female (hole) and which carry a male threaded stud."
    )
    hole_type: Literal["tap", "clearance", "heat_set_insert"] = Field(
        "tap",
        description=(
            "Female ends: tap = tap-drill size for a tap or self-tapping screw; clearance = plain through hole "
            "(a spacer, female_female only); heat_set_insert = sized for a brass heat-set insert."
        ),
    )
    stud_length: float = mm(6.0, 2.0, 30.0, "Length of each male threaded stud.")
    clearance: float = clearance(
        description=(
            "Diametral clearance: added to clearance holes and taken off male thread diameter; tune for your printer."
        )
    )


def _dims(p: StandoffParams) -> dict[str, float]:
    s = METRIC_SCREWS[p.thread_size]
    males = {"female_female": 0, "male_female": 1, "male_male": 2}[p.ends]
    if p.hole_type == "tap":
        hole = s.tap_hole
    elif p.hole_type == "clearance":
        hole = s.clearance_hole + p.clearance
    else:
        hole = s.insert_hole
    if p.ends == "female_female":
        depth = p.length if p.hole_type != "heat_set_insert" else min(p.length, s.insert_depth + 0.5)
    elif p.ends == "male_female":
        depth = min(p.length - 1.0, 3 * s.nominal) if p.hole_type != "heat_set_insert" else s.insert_depth + 0.5
    else:
        depth = 0.0
    return {
        "body_length": p.length,
        "total_length": p.length + males * p.stud_length,
        "body_size": p.body_size,
        "across_corners": p.body_size / math.cos(math.radians(30)) if p.body_shape == "hex" else p.body_size,
        "hole_diameter": hole if males < 2 else 0.0,
        "hole_depth": depth,
        "thread_major_diameter": s.nominal - p.clearance if males else 0.0,
    }


class Standoff(PartFamily):
    id = "standoff"
    name = "Standoff / spacer"
    summary = "Hex or round standoff or spacer for M2 to M5, female/female, male/female or male/male."
    description = (
        "Standoff along Z from z = 0 to length. Female ends get a tap-size hole, a heat-set insert hole, or "
        "(for a plain spacer) a clearance hole. Male ends get a modeled ISO metric thread stud, with its "
        "diameter reduced by clearance so it fits printed or metal nuts. The male stud is on top for "
        "male_female, and on both ends for male_male."
    )
    tags = ["standoff", "spacer", "hex standoff", "pcb standoff", "heat set insert", "threaded", "male", "female"]
    standards = ["M2", "M2.5", "M3", "M4", "M5", "ISO 261", "heat-set insert"]
    compatibility = [
        "thread_size M3 with hole_type tap takes M3 machine or self-tapping screws.",
        "hole_type heat_set_insert fits common brass inserts (M3: 4.0 mm hole, 5 mm deep).",
        "Male studs screw into a matching female standoff or nut of the same thread_size.",
        "Common PCB standoffs: M2.5 or M3, 5.5 mm hex (M3) or 5 mm hex (M2.5).",
    ]
    printability = Printability(
        orientation="Standing on one end (Z up), male stud up. No supports needed.",
        supports_needed=False,
        notes=[
            "Modeled threads below M3 do not print reliably on FDM printers; prefer tap or insert holes there.",
            "male_male: the bottom stud's first thread touches the bed; use a brim or print two male_female parts.",
        ],
    )
    Params = StandoffParams
    generator_version = "1"
    computed_dimensions = {
        "body_length": "Body length.",
        "total_length": "Overall length including male studs.",
        "body_size": "Across flats (hex) or diameter (round).",
        "across_corners": "Largest width of the body (equals body_size for round).",
        "hole_diameter": "Female hole diameter (0 for male_male).",
        "hole_depth": "Depth of each female hole (equals body length when it goes through).",
        "thread_major_diameter": "Male stud thread major diameter after clearance (0 without studs).",
    }

    def computed(self, p: StandoffParams) -> dict[str, float]:
        return {k: round(v, 4) for k, v in _dims(p).items()}

    def check(self, p: StandoffParams) -> list[ParamIssue]:
        d = _dims(p)
        s = METRIC_SCREWS[p.thread_size]
        issues: list[ParamIssue] = []
        inner = max(d["hole_diameter"], s.nominal if p.ends != "female_female" else 0.0)
        need = inner + 2 * MIN_WALL
        if p.body_size < need:
            issues.append(
                ParamIssue(
                    param="body_size",
                    code="too_small",
                    message=(
                        f"body_size {p.body_size} mm leaves less than {MIN_WALL} mm of wall around the "
                        f"{inner:.2f} mm {p.hole_type if d['hole_diameter'] >= inner else 'thread'} for {p.thread_size}. "
                        f"Use body_size >= {need:.2f} mm."
                    ),
                    allowed_min=round(need, 3),
                )
            )
        if p.hole_type == "clearance" and p.ends != "female_female":
            issues.append(
                ParamIssue(
                    param="hole_type",
                    code="incompatible",
                    message="hole_type clearance makes a plain spacer and needs ends female_female; use tap or heat_set_insert.",
                )
            )
        if p.ends == "male_female":
            need_len = (s.insert_depth + 0.5 if p.hole_type == "heat_set_insert" else 2 * s.nominal) + 1.0
            if p.length < need_len:
                issues.append(
                    ParamIssue(
                        param="length",
                        code="too_small",
                        message=f"length {p.length} mm is too short for a female {p.thread_size} end plus a stud base. Use length >= {need_len:.2f} mm.",
                        allowed_min=round(need_len, 3),
                    )
                )
        if p.ends != "female_female" and p.stud_length < 4 * s.pitch:
            issues.append(
                ParamIssue(param="stud_length", code="too_small", message="stud_length must cover at least 4 thread pitches.",
                           allowed_min=round(4 * s.pitch, 3))
            )
        return issues

    def warnings(self, p: StandoffParams) -> list[str]:
        if p.ends != "female_female" and METRIC_SCREWS[p.thread_size].nominal < 3:
            return [f"Modeled {p.thread_size} male threads are at the limit of FDM printing and may not engage."]
        return []

    @staticmethod
    def _stud(p: StandoffParams, z0: float, up: bool) -> bd.Part:
        from bd_warehouse.thread import IsoThread

        logging.getLogger("bd_warehouse").setLevel(logging.WARNING)
        s = METRIC_SCREWS[p.thread_size]
        th = IsoThread(
            major_diameter=s.nominal - p.clearance,
            pitch=s.pitch,
            length=p.stud_length,
            external=True,
            end_finishes=("fade", "fade"),
        )
        core: bd.Part = bd.Cylinder(
            th.min_radius + 0.001, p.stud_length, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)
        )
        for solid in th.solids():
            core = core + solid
        if up:
            return bd.Pos(0, 0, z0 - 0.01) * core
        return bd.Pos(0, 0, z0 + 0.01) * bd.Rot(180, 0, 0) * core

    def build(self, p: StandoffParams) -> bd.Part:
        d = _dims(p)
        bottom = {"align": (bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)}
        if p.body_shape == "hex":
            body = bd.extrude(bd.RegularPolygon(d["across_corners"] / 2, 6), amount=p.length)
        else:
            body = bd.Cylinder(p.body_size / 2, p.length, **bottom)
        s = METRIC_SCREWS[p.thread_size]
        hole_r = d["hole_diameter"] / 2
        if p.ends == "female_female":
            if p.hole_type == "heat_set_insert":
                body = body - bd.Pos(0, 0, -1) * bd.Cylinder(hole_r, d["hole_depth"] + 1, **bottom)
                body = body - bd.Pos(0, 0, p.length - d["hole_depth"]) * bd.Cylinder(hole_r, d["hole_depth"] + 1, **bottom)
                body = body - bd.Pos(0, 0, -1) * bd.Cylinder(s.tap_hole / 2, p.length + 2, **bottom)
            else:
                body = body - bd.Pos(0, 0, -1) * bd.Cylinder(hole_r, p.length + 2, **bottom)
        elif p.ends == "male_female":
            body = body - bd.Pos(0, 0, -1) * bd.Cylinder(hole_r, d["hole_depth"] + 1, **bottom)
            body = body + self._stud(p, p.length, up=True)
        else:
            body = body + self._stud(p, p.length, up=True) + self._stud(p, 0.0, up=False)
        return body


PART = Standoff()
