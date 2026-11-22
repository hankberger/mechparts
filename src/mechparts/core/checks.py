"""Cross-parameter checks shared by several part families (hubs, set screws, bores)."""

from __future__ import annotations

from mechparts.core.models import ParamIssue
from mechparts.core.standards import METRIC_SCREWS

MIN_WALL = 1.0  # mm of material required between features


def check_hub(
    hub_diameter: float, hub_length: float, bore_actual: float, max_diameter: float, max_reason: str
) -> list[ParamIssue]:
    """A hub needs both dimensions, a wall around the bore, and must stay under ``max_diameter``."""
    issues: list[ParamIssue] = []
    if hub_diameter <= 0 and hub_length <= 0:
        return issues
    if hub_diameter <= 0 or hub_length <= 0:
        missing = "hub_diameter" if hub_diameter <= 0 else "hub_length"
        return [
            ParamIssue(
                param=missing,
                code="missing",
                message="A hub needs both hub_diameter and hub_length > 0 (set both to 0 for no hub).",
            )
        ]
    min_hub = bore_actual + 2 * MIN_WALL
    if hub_diameter < min_hub:
        issues.append(
            ParamIssue(
                param="hub_diameter",
                code="too_small",
                message=(
                    f"hub_diameter {hub_diameter} mm leaves less than {MIN_WALL} mm of wall around the "
                    f"{bore_actual:.2f} mm bore. Use hub_diameter >= {min_hub:.2f} mm."
                ),
                allowed_min=round(min_hub, 3),
            )
        )
    if hub_diameter > max_diameter:
        issues.append(
            ParamIssue(
                param="hub_diameter",
                code="too_large",
                message=(
                    f"hub_diameter {hub_diameter} mm exceeds {max_reason} ({max_diameter:.3f} mm). "
                    f"Use hub_diameter <= {max_diameter:.3f} mm."
                ),
                allowed_max=round(max_diameter, 3),
            )
        )
    return issues


def check_set_screw(
    size: str,
    bore_diameter: float,
    bore_actual: float,
    outer_diameter: float,
    length: float,
    where: str,
    outer_param: str | None,
    length_param: str,
) -> list[ParamIssue]:
    """A radial set screw needs a bore, a wall at least one screw diameter thick, and room along the axis.

    ``outer_param`` None means the screw goes through the part body, so adding a hub is the fix."""
    screw = METRIC_SCREWS[size]
    if bore_diameter <= 0:
        return [ParamIssue(param="set_screw", code="requires_bore", message="set_screw needs bore_diameter > 0.")]
    issues: list[ParamIssue] = []
    wall = (outer_diameter - bore_actual) / 2
    if wall < screw.nominal:
        need = bore_actual + 2 * screw.nominal
        fix = f"Use {outer_param} >= {need:.2f} mm" if outer_param else f"Add a hub with hub_diameter >= {need:.2f} mm"
        issues.append(
            ParamIssue(
                param=outer_param or "hub_diameter",
                code="too_small",
                message=(
                    f"The {where} wall is {wall:.2f} mm, too thin for an {size} set screw (needs {screw.nominal} mm "
                    f"of thread). {fix} or a smaller set_screw_size."
                ),
                allowed_min=round(need, 3),
            )
        )
    need_len = screw.tap_hole + 2 * 0.8
    if length < need_len:
        issues.append(
            ParamIssue(
                param=length_param,
                code="too_small",
                message=f"The {where} is {length} mm long; an {size} set screw hole needs at least {need_len:.2f} mm.",
                allowed_min=round(need_len, 3),
            )
        )
    return issues


def check_d_flat(bore_type: str, bore_diameter: float, d_flat_depth: float) -> list[ParamIssue]:
    if bore_type != "d_shaft":
        return []
    if bore_diameter <= 0:
        return [ParamIssue(param="bore_type", code="requires_bore", message="bore_type d_shaft needs bore_diameter > 0.")]
    if d_flat_depth >= bore_diameter / 2:
        return [
            ParamIssue(
                param="d_flat_depth",
                code="too_large",
                message=f"d_flat_depth must be less than half of bore_diameter ({bore_diameter / 2} mm).",
                allowed_max=round(bore_diameter / 2 - 0.01, 3),
            )
        ]
    return []
