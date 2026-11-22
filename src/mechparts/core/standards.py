"""Reference dimensions for metric fasteners and ball bearings, tuned for FDM printing.

Hole sizes here are nominal; part generators add the user's ``clearance`` where a
fit matters (bores, bearing seats). Tap holes are deliberately left at tap-drill
size so screws can cut or form their own threads in plastic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricScrew:
    size: str
    nominal: float  # major diameter
    clearance_hole: float  # normal-fit clearance hole (ISO 273 medium)
    tap_hole: float  # tap drill / thread-forming pilot
    nut_af: float  # hex nut width across flats (ISO 4032)
    nut_thickness: float
    insert_hole: float  # typical brass heat-set insert hole diameter
    insert_depth: float
    head_diameter: float  # socket head cap screw head
    pitch: float


METRIC_SCREWS: dict[str, MetricScrew] = {
    s.size: s
    for s in [
        MetricScrew("M2", 2.0, 2.4, 1.6, 4.0, 1.6, 3.2, 4.0, 3.8, 0.4),
        MetricScrew("M2.5", 2.5, 2.9, 2.05, 5.0, 2.0, 3.6, 4.0, 4.5, 0.45),
        MetricScrew("M3", 3.0, 3.4, 2.5, 5.5, 2.4, 4.0, 5.0, 5.5, 0.5),
        MetricScrew("M4", 4.0, 4.5, 3.3, 7.0, 3.2, 5.6, 6.0, 7.0, 0.7),
        MetricScrew("M5", 5.0, 5.5, 4.2, 8.0, 4.0, 6.4, 7.0, 8.5, 0.8),
    ]
}


@dataclass(frozen=True)
class Bearing:
    designation: str
    bore: float
    outer_diameter: float
    width: float


BEARINGS: dict[str, Bearing] = {
    b.designation: b
    for b in [
        Bearing("608", 8.0, 22.0, 7.0),
        Bearing("625", 5.0, 16.0, 5.0),
        Bearing("688", 8.0, 16.0, 5.0),
    ]
}
