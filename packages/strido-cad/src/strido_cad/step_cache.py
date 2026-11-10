"""Tessellate every solid of a STEP file once and cache the meshes.

Reading and meshing the 32 MB upstream STEP takes minutes; downstream tools
(assembly composition, interference checks, renders) only need triangle meshes
of individual solids in assembly coordinates. The cache lives in `build/` and is
keyed by the STEP file hash, so it never goes stale silently.
"""

import hashlib
import json
import sys
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer

from .features import solid_volume_mm3
from .paths import CAD_CACHE
from .step_tree import read_step_leaves

CACHE_ROOT = CAD_CACHE / "step_cache"
LINEAR_DEFLECTION_MM = 0.05
ANGULAR_DEFLECTION_RAD = 0.2


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()[:16]


def tessellate(shape) -> trimesh.Trimesh:
    vertices, triangles = cq.Shape.cast(shape).tessellate(LINEAR_DEFLECTION_MM, ANGULAR_DEFLECTION_RAD)
    mesh = trimesh.Trimesh(np.array([[v.x, v.y, v.z] for v in vertices]), np.array(triangles), process=True)
    mesh.merge_vertices()
    return mesh


def load_step_cache(step_path: Path) -> list[dict]:
    """Return the manifest of cached solids for a STEP file, building it if needed.

    Each entry: {key, step_path, solid, name, volume_mm3, stl (absolute path)}.
    """
    step_path = step_path.resolve()
    digest = file_digest(step_path)
    cache_dir = CACHE_ROOT / f"{step_path.stem}-{digest}"
    manifest_path = cache_dir / "manifest.json"
    if manifest_path.is_file():
        return json.loads(manifest_path.read_text())
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for leaf in read_step_leaves(step_path):
        explorer = TopExp_Explorer(leaf.shape, TopAbs_SOLID)
        solid_index = 0
        while explorer.More():
            solid = explorer.Current()
            explorer.Next()
            mesh = tessellate(solid)
            key = f"{len(manifest):04d}"
            stl_path = cache_dir / f"{key}.stl"
            mesh.export(stl_path)
            manifest.append(
                {
                    "key": key,
                    "step_path": leaf.path_str,
                    "solid": solid_index,
                    "name": leaf.name,
                    "volume_mm3": round(solid_volume_mm3(solid), 2),
                    "stl": str(stl_path),
                }
            )
            solid_index += 1
    manifest_path.write_text(json.dumps(manifest, indent=1))
    return manifest


if __name__ == "__main__":
    for argument in sys.argv[1:]:
        entries = load_step_cache(Path(argument))
        print(f"{argument}: {len(entries)} solids cached")
