"""Shortest clear path for a cable between two route points on the robot base.

The space a cable may use is the inside of the robot minus every base part and minus every
volume a leg part sweeps over the joint ranges of hardware/joint_limits.yaml (hips in 1° steps,
thigh/calf over a grid). It is voxelised at `PITCH_MM`; a voxel is usable for a cable of radius r
when its distance to the nearest occupied voxel is at least r + `MARGIN_MM`. A path is the
cheapest 6-connected walk through usable voxels (Dijkstra on a box around both ends), where a
step costs more the farther it is from any surface (cables are tied along structure, not strung
through the middle of a cavity), then shortened by line-of-sight shortcuts through usable space.

The occupancy grid is cached in build/cad/wiring/occupancy.npz, keyed by the assembly digest.
The router only proposes geometry; the wiring gate checks the result against the meshes in
every pose independently.
"""

import heapq

import numpy as np
import trimesh
import yaml
from scipy import ndimage

from .assembly import Instance, body_transforms, load_mesh
from .paths import JOINT_LIMITS

PITCH_MM = 1.0
MARGIN_MM = 0.3
WALL_BAND_MM = 3.0  # within this distance of a surface a step costs its length
WALL_PENALTY = 0.6  # extra cost per step at >= WALL_BAND_MM + 6 mm from any surface
SEARCH_PAD_MM = 40.0
END_RELIEF_MM = 4.0  # near either end the path may pass closer (it leaves a connector face)
SURFACE_STEP_MM = 0.5
HIP_STEPS = 69
THIGH_STEPS, CALF_STEPS, COARSE_HIP_STEPS = 6, 5, 9


class Occupancy:
    def __init__(self, low: np.ndarray, shape: tuple[int, int, int], occupied: np.ndarray):
        self.low = low
        self.shape = shape
        self.occupied = occupied
        self.clearance = ndimage.distance_transform_edt(~occupied) * PITCH_MM

    def index(self, points: np.ndarray) -> np.ndarray:
        return np.clip(np.floor((points - self.low) / PITCH_MM).astype(int), 0, np.array(self.shape) - 1)

    def centre(self, index) -> np.ndarray:
        return self.low + (np.asarray(index) + 0.5) * PITCH_MM

    def clear_at(self, points: np.ndarray) -> np.ndarray:
        k = self.index(np.atleast_2d(points))
        return self.clearance[k[:, 0], k[:, 1], k[:, 2]]


def _surface_points(mesh: trimesh.Trimesh) -> np.ndarray:
    vertices, _ = trimesh.remesh.subdivide_to_size(mesh.vertices, mesh.faces, max_edge=SURFACE_STEP_MM)
    return vertices


def _angle(limits: list[float], step: int, steps: int) -> float:
    low, high = limits
    return float(np.radians(low + (high - low) * step / max(steps - 1, 1)))


def _poses(limits: dict, steps_hip: int, steps_thigh: int, steps_calf: int):
    """A grid of (hip, thigh, calf) poses over the joint ranges, all legs at the same grid point."""
    for h in range(steps_hip):
        for t in range(steps_thigh):
            for c in range(steps_calf):
                yield {
                    leg: (
                        _angle(entry["hip_deg"], h, steps_hip),
                        _angle(entry["thigh_deg"], t, steps_thigh),
                        _angle(entry["calf_deg"], c, steps_calf),
                    )
                    for leg, entry in limits.items()
                }


def build(assembly: list[Instance], stand: dict) -> Occupancy:
    """Occupancy of the base parts plus the swept leg parts, on a grid around the base."""
    base = [i for i in assembly if i.body == "base" and i.kind not in ("reference", "cable")]
    corners = []
    for item in base:
        corners.append(trimesh.transform_points(trimesh.bounds.corners(load_mesh(item.mesh).bounds), item.matrix))
    corners = np.concatenate(corners)
    low = corners.min(axis=0) - 2.0
    shape = tuple(np.ceil((corners.max(axis=0) + 2.0 - low) / PITCH_MM).astype(int))
    occupied = np.zeros(shape, dtype=bool)

    def mark(points):
        k = np.floor((points - low) / PITCH_MM).astype(int)
        inside = np.all((k >= 0) & (k < np.array(shape)), axis=1)
        k = k[inside]
        occupied[k[:, 0], k[:, 1], k[:, 2]] = True

    for item in base:
        mesh = load_mesh(item.mesh).copy().apply_transform(item.matrix)
        mark(_surface_points(mesh))
    moving = {}
    for item in assembly:
        if item.body == "base" or item.kind in ("reference", "cable"):
            continue
        points = _surface_points(load_mesh(item.mesh).copy().apply_transform(item.matrix))
        moving.setdefault(item.body, []).append(points)
    moving = {body: np.unique(np.round(np.concatenate(p) / 0.7), axis=0) * 0.7 for body, p in moving.items()}
    limits = yaml.safe_load(JOINT_LIMITS.read_text())["limits"]
    hip_only = {
        leg: {**e, "thigh_deg": [np.degrees(stand[leg][1])] * 2, "calf_deg": [np.degrees(stand[leg][2])] * 2}
        for leg, e in limits.items()
    }
    sweeps = [(pose, True) for pose in _poses(hip_only, HIP_STEPS, 1, 1)]
    sweeps += [(pose, False) for pose in _poses(limits, COARSE_HIP_STEPS, THIGH_STEPS, CALF_STEPS)]
    for pose, hips_only in sweeps:
        transforms = body_transforms(pose)
        for body, points in moving.items():
            if hips_only and not body.endswith(".hip"):
                continue
            matrix = transforms[body]
            mark(points @ matrix[:3, :3].T + matrix[:3, 3])
    return Occupancy(low, shape, occupied)


def _usable(occupancy: Occupancy, radius: float, a: np.ndarray, b: np.ndarray, box) -> np.ndarray:
    lo, hi = box
    clearance = occupancy.clearance[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]]
    usable = clearance >= radius + MARGIN_MM
    grid = np.stack(np.meshgrid(*[np.arange(lo[i], hi[i]) for i in range(3)], indexing="ij"), axis=-1)
    centres = occupancy.low + (grid + 0.5) * PITCH_MM
    for end in (a, b):
        near = np.linalg.norm(centres - end, axis=-1) <= END_RELIEF_MM
        usable |= near & (clearance >= PITCH_MM * 0.5)
    return usable


def route(occupancy: Occupancy, a: np.ndarray, b: np.ndarray, radius: float) -> np.ndarray:
    """Polyline from a to b (both included) through usable space; raises if there is none."""
    pad = SEARCH_PAD_MM
    lo = occupancy.index(np.minimum(a, b) - pad)
    hi = occupancy.index(np.maximum(a, b) + pad) + 1
    usable = _usable(occupancy, radius, a, b, (lo, hi))
    clearance = occupancy.clearance[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]]
    start = tuple(occupancy.index(a[None])[0] - lo)
    goal = tuple(occupancy.index(b[None])[0] - lo)
    assert usable[start] and usable[goal], f"route end blocked at {a if not usable[start] else b}"
    step_cost = PITCH_MM * (1.0 + WALL_PENALTY * np.clip((clearance - radius - WALL_BAND_MM) / 6.0, 0.0, 1.0))
    best = np.full(usable.shape, np.inf)
    parent = {}
    best[start] = 0.0
    frontier = [(0.0, start)]
    goal_point = np.array(goal)
    moves = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    while frontier:
        _, node = heapq.heappop(frontier)
        if node == goal:
            break
        cost = best[node]
        for dx, dy, dz in moves:
            nxt = (node[0] + dx, node[1] + dy, node[2] + dz)
            if not (0 <= nxt[0] < usable.shape[0] and 0 <= nxt[1] < usable.shape[1] and 0 <= nxt[2] < usable.shape[2]):
                continue
            if not usable[nxt]:
                continue
            candidate = cost + step_cost[nxt]
            if candidate < best[nxt]:
                best[nxt] = candidate
                parent[nxt] = node
                heuristic = PITCH_MM * float(np.abs(np.array(nxt) - goal_point).sum())
                heapq.heappush(frontier, (candidate + heuristic, nxt))
    assert np.isfinite(best[goal]), f"no clear route of radius {radius} mm from {a.round(1)} to {b.round(1)}"
    cells = [goal]
    while cells[-1] != start:
        cells.append(parent[cells[-1]])
    points = [occupancy.centre(np.array(c) + lo) for c in reversed(cells)]
    points[0], points[-1] = a, b
    return _shortcut(occupancy, np.array(points), radius)


def _visible(occupancy: Occupancy, p: np.ndarray, q: np.ndarray, radius: float, ends, farthest: float) -> bool:
    """Straight p-q keeps the cable clear and no farther from the structure than the searched path."""
    count = max(2, int(np.linalg.norm(q - p) / (PITCH_MM * 0.5)) + 1)
    samples = p + (q - p) * np.linspace(0.0, 1.0, count)[:, None]
    near_end = np.min([np.linalg.norm(samples - e, axis=1) for e in ends], axis=0) <= END_RELIEF_MM
    need = np.where(near_end, PITCH_MM * 0.5, radius + MARGIN_MM)
    clearance = occupancy.clear_at(samples)
    return bool(np.all(clearance >= need) and clearance.max() <= farthest + PITCH_MM)


def _shortcut(occupancy: Occupancy, points: np.ndarray, radius: float) -> np.ndarray:
    ends = (points[0], points[-1])
    along = occupancy.clear_at(points)
    result = [points[0]]
    i = 0
    while i < len(points) - 1:
        j = len(points) - 1
        while j > i + 1 and not _visible(occupancy, points[i], points[j], radius, ends, along[i : j + 1].max()):
            j -= 1
        result.append(points[j])
        i = j
    return np.array(result)
