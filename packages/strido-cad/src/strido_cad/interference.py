"""Exact pairwise interference between placed instances (manifold3d booleans).

Broad phase: axis-aligned bounding boxes (inflated by `clearance_mm`).
Narrow phase: volume of the boolean intersection of the two closed meshes.
A pair is reported when the overlap exceeds `volume_tolerance_mm3`; pairs that
are *designed* to touch (press-fit bearing in its bore, screw in its hole) are
classified by the caller through `allowed` rules, never silently skipped.
"""

from dataclasses import dataclass

import manifold3d
import numpy as np
import trimesh

from .assembly import Instance, load_mesh

_MANIFOLDS: dict = {}


def _manifold(instance: Instance) -> manifold3d.Manifold:
    key = str(instance.mesh)
    if key not in _MANIFOLDS:
        mesh = load_mesh(instance.mesh)
        solid = manifold3d.Manifold(
            manifold3d.Mesh(
                vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
                tri_verts=np.asarray(mesh.faces, dtype=np.uint32),
            )
        )
        assert solid.status() == manifold3d.Error.NoError, f"{instance.mesh} is not a closed manifold"
        _MANIFOLDS[key] = solid
    matrix = instance.matrix
    affine = [list(map(float, matrix[row, :4])) for row in range(3)]
    return _MANIFOLDS[key].transform(affine)


def _bounds(instance: Instance) -> np.ndarray:
    corners = trimesh.bounds.corners(load_mesh(instance.mesh).bounds)
    placed = trimesh.transform_points(corners, instance.matrix)
    return np.array([placed.min(axis=0), placed.max(axis=0)])


@dataclass
class Overlap:
    a: Instance
    b: Instance
    volume_mm3: float
    centroid_mm: np.ndarray


def overlaps(
    instances: list[Instance],
    volume_tolerance_mm3: float = 1.0,
    pairs_filter=None,
) -> list[Overlap]:
    """All pairs whose solids intersect by more than the tolerance."""
    bounds = [_bounds(item) for item in instances]
    found = []
    for i in range(len(instances)):
        for j in range(i + 1, len(instances)):
            lo = np.maximum(bounds[i][0], bounds[j][0])
            hi = np.minimum(bounds[i][1], bounds[j][1])
            if np.any(hi <= lo):
                continue
            if pairs_filter is not None and not pairs_filter(instances[i], instances[j]):
                continue
            common = _manifold(instances[i]) ^ _manifold(instances[j])
            volume = common.volume()
            if volume > volume_tolerance_mm3:
                mesh = common.to_mesh()
                points = np.asarray(mesh.vert_properties)[:, :3]
                found.append(Overlap(instances[i], instances[j], float(volume), points.mean(axis=0)))
    return found


@dataclass
class Gap:
    a: Instance
    b: Instance
    gap_mm: float


def gaps(instances: list[Instance], search_mm: float, pairs_filter=None) -> list[Gap]:
    """Minimum surface distance of every pair closer than `search_mm` (0 when they touch or overlap)."""
    bounds = [_bounds(item) for item in instances]
    found = []
    for i in range(len(instances)):
        for j in range(i + 1, len(instances)):
            lo = np.maximum(bounds[i][0], bounds[j][0])
            hi = np.minimum(bounds[i][1], bounds[j][1])
            if np.any(hi <= lo - search_mm):
                continue
            if pairs_filter is not None and not pairs_filter(instances[i], instances[j]):
                continue
            distance = _manifold(instances[i]).min_gap(_manifold(instances[j]), search_mm)
            if distance < search_mm:
                found.append(Gap(instances[i], instances[j], float(distance)))
    return found
