"""Render a PNG preview of every part family with default parameters.

    uv run --group dev python scripts/render_previews.py [--out previews] [--part spur_gear]

Uses a small orthographic painter's-algorithm renderer on top of matplotlib, so it works
headless with no OpenGL. Output: <out>/<part_id>.png
"""

from __future__ import annotations

import argparse
import io
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import trimesh  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402

from mechparts.core import registry  # noqa: E402
from mechparts.core.geometry import export_bytes  # noqa: E402

BASE = np.array([0.23, 0.47, 0.80])  # steel blue
LIGHT = np.array([-0.4, -0.5, 0.75])


def view_matrix(elev_deg: float, azim_deg: float) -> np.ndarray:
    e, a = math.radians(elev_deg), math.radians(azim_deg)
    rz = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    rx = np.array([[1, 0, 0], [0, math.cos(e), -math.sin(e)], [0, math.sin(e), math.cos(e)]])
    return rx @ rz


def render(mesh: trimesh.Trimesh, title: str, path: Path, elev: float = -60, azim: float = 35) -> None:
    m = view_matrix(elev, azim)
    v = (mesh.vertices - mesh.bounds.mean(axis=0)) @ m.T  # x right, y up, z toward viewer
    tris = v[mesh.faces]
    normals = mesh.face_normals @ m.T
    keep = normals[:, 2] > 0  # back-face culling
    tris, normals = tris[keep], normals[keep]
    order = np.argsort(tris[:, :, 2].mean(axis=1))  # far to near
    tris, normals = tris[order], normals[order]
    light = LIGHT / np.linalg.norm(LIGHT)
    diffuse = np.clip(normals @ (m @ light), 0, 1)  # light is fixed relative to the viewer
    shade = 0.35 + 0.65 * diffuse
    colors = np.clip(BASE[None, :] * shade[:, None] + 0.12 * diffuse[:, None] ** 8, 0, 1)

    fig, ax = plt.subplots(figsize=(6, 6), dpi=120)
    ax.add_collection(PolyCollection(tris[:, :, :2], facecolors=colors, edgecolors=colors, linewidths=0.2))
    span = np.abs(v[:, :2]).max() * 1.08
    ax.set_xlim(-span, span)
    ax.set_ylim(-span, span)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="previews")
    ap.add_argument("--part", action="append", help="Only these part ids (repeatable).")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for pid, part in registry.all_parts().items():
        if args.part and pid not in args.part:
            continue
        model = part.Params()
        shape = part.build(model)
        mesh = trimesh.load(io.BytesIO(export_bytes(shape, "stl", "preview")), file_type="stl")
        dims = part.computed(model)
        bb = mesh.extents
        title = f"{part.name} (defaults)\n{bb[0]:.1f} x {bb[1]:.1f} x {bb[2]:.1f} mm"
        path = out / f"{pid}.png"
        render(mesh, title, path)
        print(f"{path}  {len(dims)} computed dims")


if __name__ == "__main__":
    main()
