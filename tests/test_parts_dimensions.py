"""Per-family checks that generated geometry matches the requested dimensions."""

import math

import build123d as bd
import pytest

from mechparts.core import registry

TOL = 0.02


def make(part_id, **kw):
    part = registry.get(part_id)
    p = part.Params(**kw)
    assert part.check(p) == [], part.check(p)
    return p, part.build(p), part.computed(p)


def inside(shape, x, y, z):
    return shape.is_inside(bd.Vector(x, y, z))


def max_radius(shape, z):
    """Largest XY distance of any vertex at height z (within 1e-3)."""
    return max(math.hypot(v.X, v.Y) for v in shape.vertices() if abs(v.Z - z) < 1e-3)


# GT2 pulley ---------------------------------------------------------------
@pytest.mark.parametrize("teeth,belt", [(20, 6), (36, 10), (12, 6)])
def test_gt2_dimensions(teeth, belt):
    p, s, c = make("gt2_pulley", teeth=teeth, belt_width=belt, bore_diameter=3 if teeth < 16 else 5,
                   hub_diameter=0, hub_length=0, set_screw=False, flanges=False)
    assert c["pitch_diameter"] == pytest.approx(teeth * 2 / math.pi, abs=1e-3)
    assert c["outer_diameter"] == pytest.approx(c["pitch_diameter"] - 0.508, abs=1e-3)
    bb = s.bounding_box()
    assert bb.size.Z == pytest.approx(belt + 1, abs=TOL)
    zmid = bb.size.Z / 2
    assert max_radius(s, 0.0) == pytest.approx(c["outer_diameter"] / 2, abs=TOL)
    # Exactly `teeth` grooves: sample just under the OD around the circle.
    r = c["outer_diameter"] / 2 - 0.3
    states = [inside(s, r * math.cos(a), r * math.sin(a), zmid) for a in [2 * math.pi * k / 720 for k in range(720)]]
    transitions = sum(1 for i in range(720) if states[i] and not states[i - 1])
    assert transitions == teeth
    assert inside(s, c["root_diameter"] / 2 - 0.2, 0, zmid)


def test_gt2_flanges_and_hub():
    p, s, c = make("gt2_pulley")
    bb = s.bounding_box()
    assert bb.size.X == pytest.approx(c["flange_diameter"], abs=TOL)
    assert bb.size.Z == pytest.approx(c["total_length"], abs=TOL)
    assert not inside(s, 0, 0, 1)  # bore
    assert not inside(s, 0, 5.0, p.hub_length / 2)  # set screw hole along +Y in the hub
    assert inside(s, 0, -5.0, p.hub_length / 2)


# Shaft coupler ------------------------------------------------------------
@pytest.mark.parametrize("style", ["set_screw", "clamp"])
def test_coupler_bores(style):
    p, s, c = make("shaft_coupler", style=style, bore_a=5, bore_b=8, outer_diameter=24, length=30)
    bb = s.bounding_box()
    assert bb.size.Z == pytest.approx(30, abs=TOL)
    assert bb.size.X == pytest.approx(24, abs=TOL)
    ra, rb = c["bore_a_actual_diameter"] / 2, c["bore_b_actual_diameter"] / 2
    assert not inside(s, -(ra - 0.05), 0, 3) and inside(s, -(ra + 0.05), 0, 3)
    assert not inside(s, -(rb - 0.05), 0, 27) and inside(s, -(rb + 0.05), 0, 27)
    if style == "clamp":
        assert c["clamp_screw_max_length"] > 0
        assert not inside(s, 0, 11, 3)  # axial slit on +Y
        assert inside(s, 0, -11, 3)


# Bearing mount ------------------------------------------------------------
@pytest.mark.parametrize("bearing,od", [("608", 22), ("625", 16), ("688", 16)])
def test_bearing_mount_seat(bearing, od):
    p, s, c = make("bearing_mount", bearing=bearing, mounting_hole_spacing=45)
    h = c["shaft_height"]
    seat_r = (od + p.bearing_clearance) / 2
    assert c["seat_diameter"] == pytest.approx(od + p.bearing_clearance)
    y_seat = -c["width"] / 2 + 1.0  # inside the open side of the seat
    assert not inside(s, seat_r - 0.05, y_seat, h)
    assert inside(s, seat_r + 0.05, y_seat, h)
    assert inside(s, c["shoulder_diameter"] / 2 + 0.05, c["width"] / 2 - 0.5, h)  # shoulder lip
    bb = s.bounding_box()
    assert bb.size.X == pytest.approx(c["base_length"], abs=TOL)
    assert bb.size.Z == pytest.approx(2 * h, abs=TOL)
    assert not inside(s, 22.5, 0, p.base_thickness / 2)  # mounting hole


# Standoff -----------------------------------------------------------------
@pytest.mark.parametrize("shape", ["hex", "round"])
def test_standoff_female(shape):
    p, s, c = make("standoff", body_shape=shape, body_size=6, length=12)
    bb = s.bounding_box()
    assert bb.size.Z == pytest.approx(12, abs=TOL)
    assert bb.size.Y == pytest.approx(6, abs=TOL)
    if shape == "hex":
        assert bb.size.X == pytest.approx(6 / math.cos(math.radians(30)), abs=TOL)
    assert not inside(s, c["hole_diameter"] / 2 - 0.05, 0, 6)
    assert inside(s, c["hole_diameter"] / 2 + 0.05, 0, 6)


def test_standoff_male_thread():
    p, s, c = make("standoff", ends="male_female")
    bb = s.bounding_box()
    assert bb.size.Z == pytest.approx(c["total_length"], abs=0.05)
    assert bb.max.X >= 0  # sanity
    zs = [v for v in s.vertices() if v.Z > p.length + 1]
    assert max(math.hypot(v.X, v.Y) for v in zs) == pytest.approx(c["thread_major_diameter"] / 2, abs=0.05)


def test_standoff_heat_set():
    p, s, c = make("standoff", hole_type="heat_set_insert", body_size=6.5, length=15)
    assert not inside(s, 1.9, 0, 2)  # insert hole (4.0 mm) at the bottom end
    assert inside(s, 1.9, 0, 7.5)  # only the pilot hole in the middle


# L-bracket ----------------------------------------------------------------
def test_l_bracket_holes_and_size():
    p, s, c = make("l_bracket", leg_a=40, leg_b=30, width=20, thickness=4, holes_per_leg=2, gusset=True)
    bb = s.bounding_box()
    assert (bb.size.X, bb.size.Y, bb.size.Z) == pytest.approx((40, 20, 30), abs=TOL)
    assert c["first_hole_a"] == pytest.approx(4 + 36 / 4)
    for i in range(2):
        x = c["first_hole_a"] + i * c["hole_spacing_a"]
        assert not inside(s, x, 0, 2)
        z = c["first_hole_b"] + i * c["hole_spacing_b"]
        assert not inside(s, 2, 0, z)
    assert inside(s, 5, 9, 5)  # gusset at +Y edge
    assert not inside(s, 5, 0, 5)  # open between gussets
