"""Brute-force rack-cutting simulation used to check the analytic gear profile."""

import math

import numpy as np
from shapely.affinity import rotate, translate
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union


def simulated_half_angles(g, radii, steps=1500):
    r, a, p = g.pitch_radius, g.alpha, g.circular_pitch
    hf = g.dedendum_coef * g.module
    c = p / 4 - hf * math.tan(a)
    top = 3.0 * g.module
    w = p / 4 + top * math.tan(a)
    tooth = Polygon([(-c, r - hf), (c, r - hf), (w, r + top), (-w, r + top)])
    span = 2.5 * p / r
    cuts = [
        rotate(translate(tooth, r * phi, 0), phi, origin=(0, 0), use_radians=True)
        for phi in np.linspace(-span, span, steps)
    ]
    space = unary_union(cuts)
    centre = math.pi / 2 - math.pi / g.teeth
    out = []
    for rho in radii:
        lo, hi = 0.0, math.pi / g.teeth
        for _ in range(40):
            mid = (lo + hi) / 2
            q = Point(rho * math.cos(centre + mid), rho * math.sin(centre + mid))
            if space.contains(q):
                hi = mid
            else:
                lo = mid
        out.append((lo + hi) / 2)
    return out
