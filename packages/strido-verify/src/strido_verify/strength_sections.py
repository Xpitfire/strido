"""Section properties of printed links for the strength check: second moments of polygons with holes
and the weakest section of a link, scanned across its long axis in its print orientation."""

import math
from dataclasses import dataclass

import numpy as np
import trimesh
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.polygon import orient

from strido.workspace import path

STL_DIR = path("hardware/print/stl")
SECTION_SAMPLES = 41
SECTION_SPAN = (0.15, 0.85)  # sections closer to the ends are joint bosses, not the link
UP_AXIS_LIMIT = 0.5  # |z| of the long axis above this: the link stands up when printed


@dataclass
class Section:
    area_mm2: float  # smallest load-carrying area along the link
    w_bend_mm3: float  # smallest section modulus for bending in the leg plane
    i_in_mm4: float  # in-plane second moment, harmonic mean along the link (stiffness of segments in series)
    i_out_mm4: float  # second moment across the leg plane (thin direction), harmonic mean along the link
    length_mm: float
    across_layers: bool
    pin_offset_mm: float  # distance of the mid-length section's centroid from the line through the pin bores


def ring_moments(coords) -> np.ndarray:
    """Signed area, first and second moments (A, Sx, Sy, Ixx, Iyy, Ixy) of a closed ring about the origin."""
    xy = np.asarray(coords, dtype=float)
    x, y = xy[:, 0], xy[:, 1]
    xn, yn = np.roll(x, -1), np.roll(y, -1)
    cross = x * yn - xn * y
    return np.array(
        [
            cross.sum() / 2,
            ((y + yn) * cross).sum() / 6,
            ((x + xn) * cross).sum() / 6,
            ((y * y + y * yn + yn * yn) * cross).sum() / 12,
            ((x * x + x * xn + xn * xn) * cross).sum() / 12,
            ((x * yn + 2 * x * y + 2 * xn * yn + xn * y) * cross).sum() / 24,
        ]
    )


def section_properties(shape: Polygon | MultiPolygon) -> tuple[float, np.ndarray, np.ndarray]:
    """Area, centroid and centroidal second-moment matrix J = [[∫x², ∫xy], [∫xy, ∫y²]] of polygons with holes."""
    total = np.zeros(6)
    for polygon in getattr(shape, "geoms", [shape]):
        polygon = orient(polygon, 1.0)  # exterior counter-clockwise, holes clockwise: holes subtract
        total += ring_moments(polygon.exterior.coords)
        for hole in polygon.interiors:
            total += ring_moments(hole.coords)
    area, s_x, s_y, i_xx, i_yy, i_xy = total
    cx, cy = s_y / area, s_x / area
    i_xx -= area * cy * cy
    i_yy -= area * cx * cx
    i_xy -= area * cx * cy
    return area, np.array([cx, cy]), np.array([[i_yy, i_xy], [i_xy, i_xx]])


def directional_moments(
    outer: Polygon | MultiPolygon, effective: Polygon | MultiPolygon, direction: np.ndarray
) -> tuple[float, float]:
    """(I, W) for bending that strains the fibres along the 2D unit `direction`: I = ∫(p·e)² dA over the
    load-carrying `effective` section, W = I / max |p·e| with the fibre distance from the `outer` shape."""
    _, centroid, second_moments = section_properties(effective)
    points = np.vstack([np.asarray(p.exterior.coords) for p in getattr(outer, "geoms", [outer])]) - centroid
    inertia = float(direction @ second_moments @ direction)
    return inertia, inertia / float(np.abs(points @ direction).max())


def hole_count(mesh: trimesh.Trimesh, normal: np.ndarray) -> int:
    """Closed holes in the section through the centroid with this normal: pin bores show up as holes
    only in the section perpendicular to the pin axis."""
    cut = mesh.section(plane_origin=mesh.centroid, plane_normal=normal)
    return 0 if cut is None else sum(len(polygon.interiors) for polygon in cut.to_2D()[0].polygons_full)


def weakest_section(part: str, wall_mm: float) -> Section:
    """Scan sections across the part's long axis; walls of `wall_mm` carry the load, infill does not.

    Of the two short principal directions, the one along the joint pins (the direction whose
    perpendicular section shows the pin bores as holes) points across the leg plane; the other is
    the link's width in the leg plane, the bending direction of leg loads."""
    mesh = trimesh.load_mesh(STL_DIR / f"{part}.stl")
    centre = mesh.centroid
    _, vectors = np.linalg.eigh(np.cov((mesh.vertices - centre).T))
    first, second, axis = vectors[:, 0], vectors[:, 1], vectors[:, 2]
    thin, width = (first, second) if hole_count(mesh, first) >= hole_count(mesh, second) else (second, first)
    projection = (mesh.vertices - centre) @ axis
    low, high = projection.min(), projection.max()
    area_min, w_min, inverse_in, inverse_out, count = math.inf, math.inf, 0.0, 0.0, 0
    for fraction in np.linspace(*SECTION_SPAN, SECTION_SAMPLES):
        cut = mesh.section(plane_origin=centre + axis * (low + fraction * (high - low)), plane_normal=axis)
        if cut is None:
            continue
        planar, to_3d = cut.to_2D()
        outer = MultiPolygon(list(planar.polygons_full)).buffer(0)
        effective = outer.difference(outer.buffer(-wall_mm))
        in_plane = (to_3d[:3, :3].T @ width)[:2]  # the 3D directions in the section's 2D frame
        across = (to_3d[:3, :3].T @ thin)[:2]
        inertia_in, modulus = directional_moments(outer, effective, in_plane / np.linalg.norm(in_plane))
        inertia_out, _ = directional_moments(outer, effective, across / np.linalg.norm(across))
        area_min, w_min = min(area_min, effective.area), min(w_min, modulus)
        inverse_in, inverse_out, count = inverse_in + 1 / inertia_in, inverse_out + 1 / inertia_out, count + 1
    assert count, f"{part}: no section found"
    return Section(
        area_min,
        w_min,
        count / inverse_in,
        count / inverse_out,
        float(high - low),
        bool(abs(axis[2]) > UP_AXIS_LIMIT),
        pin_offset(mesh, thin, axis),
    )


def pin_offset(mesh: trimesh.Trimesh, thin: np.ndarray, axis: np.ndarray) -> float:
    """How far the shaft runs beside the line through the two pin bores (in the leg plane): an axial
    force along the pins then also bends the link by F times this offset."""
    centre = mesh.centroid
    planar, to_3d = mesh.section(plane_origin=centre, plane_normal=thin).to_2D()
    bores = sorted(
        (ring for polygon in planar.polygons_full for ring in polygon.interiors), key=lambda r: -Polygon(r).area
    )[:2]
    assert len(bores) == 2, "a link has two pin bores"
    a, b = ((to_3d @ np.array([*Polygon(r).centroid.coords[0], 0.0, 1.0]))[:3] for r in bores)
    middle = mesh.section(plane_origin=centre, plane_normal=axis)
    mid_planar, mid_to_3d = middle.to_2D()
    c = (mid_to_3d @ np.array([*MultiPolygon(list(mid_planar.polygons_full)).centroid.coords[0], 0.0, 1.0]))[:3]
    line = (b - a) / np.linalg.norm(b - a)
    off = (c - a) - np.dot(c - a, line) * line
    return float(np.linalg.norm(off - np.dot(off, thin) * thin))  # in the leg plane only
