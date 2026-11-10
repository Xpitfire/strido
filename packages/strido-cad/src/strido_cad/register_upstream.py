"""Place every upstream print STL at its assembled pose from the upstream STEP.

The upstream STLs (`design/STL`) are the files people print; the upstream STEP
(`upstream/yertle/design/CAD/Yertle_Single_v2.step`) is the only file that holds assembled poses.
This tool splits every STEP leaf into solids, matches each solid to an STL by
volume, then recovers the rigid STL->assembly transform with a principal-axes
initialisation refined by ICP. Mirror-image parts (left/right) are separated by
fit quality because a proper rotation cannot map one onto the other.

Output: `hardware/assembly/upstream_placements.yaml` (committed) plus a report of
STEP solids that have no printable STL (purchased parts or unpublished parts).

Run:  uv run --locked python -m strido_cad.register_upstream
"""

import itertools

import cadquery as cq
import numpy as np
import trimesh
import yaml
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from scipy.spatial import cKDTree

from .features import solid_volume_mm3
from .paths import REPO, UPSTREAM_PLACEMENTS, UPSTREAM_STEP, UPSTREAM_STL
from .step_tree import read_step_leaves

STEP_PATH = UPSTREAM_STEP
STL_ROOT = UPSTREAM_STL
OUTPUT = UPSTREAM_PLACEMENTS

# Volume tolerance used to pair a STEP solid with an STL (the STLs were revised
# after the STEP export, so allow a few percent).
VOLUME_TOLERANCE = 0.04
# Fit quality gate: RMS surface distance after ICP. Includes STL chord error of
# curved shells (coarse upstream tessellation), so it is looser than CAD tolerance.
RMS_GATE_MM = 0.8
SAMPLE_SOURCE = 4000
SAMPLE_TARGET = 30000


def solids_of(shape):
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    solids = []
    while explorer.More():
        solids.append(explorer.Current())
        explorer.Next()
    return solids


def tessellate(shape) -> trimesh.Trimesh:
    vertices, triangles = cq.Shape.cast(shape).tessellate(0.05, 0.2)
    return trimesh.Trimesh(np.array([[v.x, v.y, v.z] for v in vertices]), np.array(triangles), process=True)


def oriented_extents(mesh: trimesh.Trimesh) -> np.ndarray:
    """Rotation-invariant size: sorted extents of the minimum-volume oriented box."""
    _, extents = trimesh.bounds.oriented_bounds(mesh)
    return np.sort(extents)


def principal_frame(points: np.ndarray):
    centre = points.mean(axis=0)
    _, _, vt = np.linalg.svd(points - centre, full_matrices=False)
    return centre, vt  # rows are principal axes


def icp(source_points, target_tree, target_points, initial, iterations=60):
    transform = initial.copy()
    for _ in range(iterations):
        moved = source_points @ transform[:3, :3].T + transform[:3, 3]
        distances, indices = target_tree.query(moved)
        matched = target_points[indices]
        keep = distances < max(1.0, np.percentile(distances, 90))
        a = moved[keep]
        b = matched[keep]
        ca, cb = a.mean(axis=0), b.mean(axis=0)
        u, _, vt = np.linalg.svd((a - ca).T @ (b - cb))
        d = np.sign(np.linalg.det(vt.T @ u.T))
        rotation = vt.T @ np.diag([1, 1, d]) @ u.T
        step = np.eye(4)
        step[:3, :3] = rotation
        step[:3, 3] = cb - rotation @ ca
        transform = step @ transform
        if np.linalg.norm(step[:3, 3]) < 1e-5 and np.allclose(rotation, np.eye(3), atol=1e-7):
            break
    moved = source_points @ transform[:3, :3].T + transform[:3, 3]
    distances, _ = target_tree.query(moved)
    return transform, float(np.sqrt(np.mean(distances**2))), float(np.max(distances))


def register(source: trimesh.Trimesh, target: trimesh.Trimesh):
    """Best proper rigid transform mapping source onto target (both mm)."""
    source_points = source.sample(SAMPLE_SOURCE, seed=1)
    target_points = target.sample(SAMPLE_TARGET, seed=2)
    tree = cKDTree(target_points)
    source_centre, source_axes = principal_frame(source_points)
    target_centre, target_axes = principal_frame(target_points)
    best = None
    for signs in itertools.product((1, -1), repeat=3):
        flipped = np.diag(signs) @ target_axes
        if np.linalg.det(flipped) * np.linalg.det(source_axes) < 0:
            continue
        rotation = flipped.T @ source_axes
        initial = np.eye(4)
        initial[:3, :3] = rotation
        initial[:3, 3] = target_centre - rotation @ source_centre
        transform, rms, worst = icp(source_points, tree, target_points, initial)
        # Symmetric check: target -> source coverage catches partial fits.
        source_tree = cKDTree(source_points @ transform[:3, :3].T + transform[:3, 3])
        back, _ = source_tree.query(target_points[:: max(1, len(target_points) // 4000)])
        score = rms + float(np.sqrt(np.mean(back**2)))
        if best is None or score < best[0]:
            best = (score, transform, rms, worst)
    return best


def main():
    stl_meshes = {}
    for path in sorted(STL_ROOT.rglob("*.stl")):
        mesh = trimesh.load(path)
        stl_meshes[str(path.relative_to(REPO))] = mesh
    leaves = read_step_leaves(STEP_PATH)
    placements = []
    unmatched = []
    for leaf in leaves:
        if "screw" in leaf.name.lower():
            continue
        for solid_index, solid in enumerate(solids_of(leaf.shape)):
            volume = solid_volume_mm3(solid)
            candidates = [
                name
                for name, mesh in stl_meshes.items()
                if abs(abs(mesh.volume) - volume) / volume < VOLUME_TOLERANCE
                or (not mesh.is_watertight and abs(mesh.convex_hull.volume) > volume)
            ]
            # Non-watertight STLs have unreliable volume; restrict them by extents.
            target = tessellate(solid)
            target_extents = oriented_extents(target)
            candidates = [
                name for name in candidates if np.all(np.abs(oriented_extents(stl_meshes[name]) - target_extents) < 2.5)
            ]
            if not candidates:
                unmatched.append(
                    {
                        "step_path": leaf.path_str,
                        "solid": solid_index,
                        "volume_mm3": round(volume, 1),
                        "extents_mm": [round(float(v), 1) for v in target_extents],
                        "centroid_mm": [round(float(v), 2) for v in target.centroid],
                    }
                )
                continue
            results = []
            for name in candidates:
                score, transform, rms, worst = register(stl_meshes[name], target)
                results.append((score, name, transform, rms, worst))
            results.sort(key=lambda item: item[0])
            score, name, transform, rms, worst = results[0]
            status = "ok" if rms <= RMS_GATE_MM else "check"
            print(f"{status:5s} rms={rms:.3f} max={worst:.2f} {name:45s} <- {leaf.path_str}#{solid_index}")
            placements.append(
                {
                    "stl": name,
                    "step_path": leaf.path_str,
                    "solid": solid_index,
                    "rms_mm": round(rms, 4),
                    "max_mm": round(worst, 3),
                    "status": status,
                    "alternatives": [(round(r[0], 3), r[1]) for r in results[1:]],
                    "matrix": [round(float(v), 6) for v in transform.flatten()],
                }
            )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "description": "Upstream print STL -> upstream STEP assembly frame (mm). Generated by strido_cad.register_upstream",
        "step": str(STEP_PATH.relative_to(REPO)),
        "rms_gate_mm": RMS_GATE_MM,
        "placements": placements,
        "step_solids_without_stl": unmatched,
    }
    OUTPUT.write_text(yaml.safe_dump(document, sort_keys=False, width=200))
    print(f"placed {len(placements)} STL instances; {len(unmatched)} STEP solids without STL")
    for item in unmatched:
        print("  no STL:", item["step_path"], item["solid"], item["volume_mm3"], item["extents_mm"])


if __name__ == "__main__":
    main()
