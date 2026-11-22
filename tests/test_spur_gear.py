import math

import build123d as bd
import pytest

from mechparts.core.involute import SpurGearGeometry
from mechparts.parts.spur_gear import PART, SpurGearParams


def build(**kw):
    p = SpurGearParams(**kw)
    assert PART.check(p) == []
    return p, PART.build(p)


def inside(shape, r, angle, z):
    return shape.is_inside(bd.Vector(r * math.cos(angle), r * math.sin(angle), z))


@pytest.mark.parametrize("teeth,module,pa", [(20, 1.0, 20), (9, 2.0, 20), (40, 0.8, 14.5), (15, 1.5, 25)])
def test_tooth_geometry(teeth, module, pa):
    p, shape = build(teeth=teeth, module=module, pressure_angle=pa, bore_diameter=0)
    g = SpurGearGeometry(module, teeth, pa)
    bb = shape.bounding_box()
    assert bb.max.X == pytest.approx(g.tip_radius, abs=0.01)  # a tooth tip sits on +X
    assert bb.size.Z == pytest.approx(p.face_width, abs=1e-6)
    z = p.face_width / 2
    pitch = 2 * math.pi / teeth
    # Tooth thickness at the pitch circle is half the circular pitch (no backlash).
    half = math.pi / (2 * teeth)
    eps = 0.02 / g.pitch_radius
    for k in range(teeth):
        a = k * pitch
        assert inside(shape, g.pitch_radius, a + half - eps, z)
        assert not inside(shape, g.pitch_radius, a + half + eps, z)
        assert inside(shape, g.root_radius - 0.02, a + pitch / 2, z)  # solid below the root circle
        assert not inside(shape, g.root_radius + 0.02, a + pitch / 2, z)  # tooth space above it


def test_root_and_tip_circles():
    p, shape = build(bore_diameter=0)
    g = SpurGearGeometry(1, 20)
    pitch = 2 * math.pi / 20
    assert not inside(shape, g.root_radius + 0.05, pitch / 2, 3)  # space centre above root is empty
    assert inside(shape, g.root_radius - 0.05, pitch / 2, 3)
    assert inside(shape, g.tip_radius - 0.05, 0, 3)
    assert not inside(shape, g.tip_radius + 0.05, 0, 3)


def test_hub_bore_and_set_screw():
    p, shape = build(bore_diameter=5, hub_diameter=12, hub_length=8, set_screw=True, set_screw_size="M3")
    bb = shape.bounding_box()
    assert bb.size.Z == pytest.approx(14)
    bore_r = (5 + 0.2) / 2
    assert not inside(shape, bore_r - 0.05, 1.0, 3)
    assert inside(shape, bore_r + 0.05, 1.0, 3)
    assert inside(shape, 5.9, math.pi, 10)  # hub wall
    assert not inside(shape, 6.1, math.pi, 10)
    # Set screw hole enters along +Y at mid-hub.
    assert not inside(shape, 4.5, math.pi / 2, 10)
    assert inside(shape, 4.5, -math.pi / 2, 10)


def test_d_shaft_flat_faces_plus_y():
    p, shape = build(bore_diameter=5, bore_type="d_shaft", d_flat_depth=0.5)
    flat = 2.5 - 0.5 + 0.1
    assert inside(shape, flat + 0.05, math.pi / 2, 3)
    assert not inside(shape, flat - 0.05, math.pi / 2, 3)
    assert not inside(shape, 2.55, -math.pi / 2, 3)  # round side keeps full radius


def test_cross_validation_messages():
    issues = PART.check(SpurGearParams(bore_diameter=16))
    assert issues[0].param == "bore_diameter" and issues[0].allowed_max == pytest.approx(15.3)
    issues = PART.check(SpurGearParams(hub_diameter=10))
    assert issues[0].code == "missing" and issues[0].param == "hub_length"
    issues = PART.check(SpurGearParams(hub_diameter=8, hub_length=5, set_screw=True))
    assert any(i.param == "hub_diameter" and i.allowed_min for i in issues)
    issues = PART.check(SpurGearParams(hub_diameter=30, hub_length=5))
    assert any(i.code == "too_large" and i.param == "hub_diameter" for i in issues)
    issues = PART.check(SpurGearParams(teeth=6, pressure_angle=30, bore_diameter=0))
    assert any(i.code == "pointed_teeth" for i in issues)


def test_computed_dimensions():
    c = PART.computed(SpurGearParams(module=2, teeth=25, hub_diameter=20, hub_length=5))
    assert c["pitch_diameter"] == 50
    assert c["outer_diameter"] == 54
    assert c["root_diameter"] == 45
    assert c["total_length"] == 11


def test_undercut_warning_uses_classical_limit():
    assert not PART.warnings(SpurGearParams(teeth=20))
    assert not PART.warnings(SpurGearParams(teeth=18))
    assert any("undercut" in w for w in PART.warnings(SpurGearParams(teeth=16)))
