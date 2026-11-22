import math

import numpy as np
import pytest

from mechparts.core.involute import SpurGearGeometry
from rack_sim import simulated_half_angles


@pytest.mark.parametrize("teeth", [6, 10, 17, 25, 60])
@pytest.mark.parametrize("pressure_angle", [14.5, 20, 25])
def test_profile_matches_rack_cutting_simulation(teeth, pressure_angle):
    """The analytic tooth profile equals what a basic rack would actually cut (incl. undercut)."""
    g = SpurGearGeometry(1.0, teeth, pressure_angle)
    radii = np.linspace(g.root_radius + 0.02, g.tip_radius - 0.01, 15)
    sim = simulated_half_angles(g, radii, steps=800)
    err = max(abs(s - g.half_angle(r)) * r for s, r in zip(sim, radii))
    assert err < 0.01  # mm of arc length; the simulation itself is coarser than that


def test_standard_dimensions():
    g = SpurGearGeometry(2.0, 30, 20)
    assert g.pitch_radius == pytest.approx(30)
    assert g.tip_radius == pytest.approx(32)
    assert g.root_radius == pytest.approx(27.5)
    assert g.base_radius == pytest.approx(30 * math.cos(math.radians(20)))
    # Tooth thickness at the pitch circle is half the circular pitch.
    assert 2 * g.half_angle(g.pitch_radius) * g.pitch_radius == pytest.approx(math.pi * 2 / 2, abs=1e-9)


def test_undercut_threshold():
    assert SpurGearGeometry(1, 12).undercut
    assert not SpurGearGeometry(1, 30).undercut
