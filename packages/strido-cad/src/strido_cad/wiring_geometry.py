"""Cable geometry of the routed harness: conductor tubes, hip loops, spiral-wrap sleeves, cable ties and
adhesive tie mounts, as assembly instances (cached in build/cad/wiring).

`strido_cad.wiring` routes the runs; this module draws them at the CAD reference pose:
* consecutive points on one rigid body are straight segments; points on two bodies (a lead crossing the
  hip joint) are a flexible loop of the length hardware/wiring.yaml prescribes, drawn as a circular arc
  bowed along the node's ``bulge``;
* each conductor is its own tube (a pair or a flat ribbon side by side, three or more cores on a ring);
* segments shared by `SLEEVE_MIN_RUNS` or more runs (and every segment of a cable marked ``sleeve``) get a
  spiral-wrap sleeve of the bundle diameter, and every tie node a cable tie. Adhesive tie mounts under
  ``mount`` nodes are purchased parts placed by `strido_cad.catalog` (the router sees them).
"""

import hashlib
import itertools
import json

import numpy as np
import trimesh

from .assembly import Instance
from .wiring import (
    CACHE,
    ELECTRONICS,
    HERE,
    SOURCE,
    Point,
    Run,
    bundle_diameter,
    load,
    mesh_stamp,
    ring_radius,
    routed,
    run_diameter,
)

SLEEVE_MIN_RUNS = 3
TUBE_SECTIONS = 10
ARC_STEPS = 12
TIE_THICKNESS_MM = 1.2
TIE_MASS_KG = 0.0003  # 2.5 x 100 mm nylon tie


def arc(a: np.ndarray, b: np.ndarray, length: float, bulge: np.ndarray) -> np.ndarray:
    """Points of a circular arc from a to b of the given length, bowed towards `bulge`."""
    chord = b - a
    c = float(np.linalg.norm(chord))
    assert length >= c, f"loop {length:.1f} mm shorter than its chord {c:.1f} mm"
    direction = chord / c
    side = bulge - np.dot(bulge, direction) * direction
    side /= np.linalg.norm(side)
    if length - c < 1e-3:
        return np.array([a, b])
    lo, hi = 1e-6, np.pi - 1e-6  # half-angle phi solves sin(phi)/phi = c/length
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if np.sin(mid) / mid > c / length else (lo, mid)
    phi = (lo + hi) / 2
    radius = length / (2 * phi)
    centre = (a + b) / 2 - side * radius * np.cos(phi)
    u = (a - centre) / radius
    w = (b - centre) / radius
    v = (w - np.cos(2 * phi) * u) / np.sin(2 * phi)  # in-plane unit vector: rotating u by 2*phi reaches w
    angles = np.linspace(0.0, 2 * phi, ARC_STEPS + 1)
    return np.array([centre + radius * (np.cos(t) * u + np.sin(t) * v) for t in angles])


def polyline(run: Run) -> list[tuple[str, bool, np.ndarray]]:
    """(body, flexible, points) pieces of a run at the CAD pose; loops are arcs."""
    pieces = []
    current = [run.points[0].xyz]
    body = run.points[0].body
    for a, b in run.segments():
        if a.body == b.body:
            current.append(b.xyz)
            continue
        pieces.append((body, False, np.array(current)))
        loop = a.loop_mm if a.loop_mm is not None else b.loop_mm
        bulge = a.bulge if a.bulge is not None else b.bulge
        assert loop is not None and bulge is not None, (
            f"{run.name}: {a.name} -> {b.name} crosses bodies without loop_mm/bulge"
        )
        pieces.append((a.body, True, arc(a.xyz, b.xyz, loop, bulge)))
        current, body = [b.xyz], b.body
    pieces.append((body, False, np.array(current)))
    return [p for p in pieces if len(p[2]) > 1]


def length_mm(points: np.ndarray) -> float:
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())


def tube(points: np.ndarray, radius: float) -> trimesh.Trimesh:
    parts = []
    for a, b in itertools.pairwise(points):
        if np.linalg.norm(b - a) > 1e-6:
            parts.append(trimesh.creation.cylinder(radius, segment=[a, b], sections=TUBE_SECTIONS))
    for p in points:
        parts.append(trimesh.creation.icosphere(subdivisions=1, radius=radius).apply_translation(p))
    return trimesh.util.concatenate(parts)


def conductors(points: np.ndarray, kind: dict) -> list[np.ndarray]:
    """Centrelines of the drawn conductors of a cable type along `points` (see `run_diameter`)."""
    count = len(kind["colours"])
    if count == 1:
        return [points]
    ring = not (kind.get("flat") or count == 2)
    strands = [[] for _ in range(count)]
    normal = None
    for k, p in enumerate(points):
        tangent = points[min(k + 1, len(points) - 1)] - points[max(k - 1, 0)]
        tangent /= np.linalg.norm(tangent)
        if normal is None:
            helper = np.array([0.0, 0.0, 1.0]) if abs(tangent[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
            normal = np.cross(tangent, helper)
        normal = normal - np.dot(normal, tangent) * tangent  # parallel transport keeps the strands untwisted
        normal /= np.linalg.norm(normal)
        binormal = np.cross(tangent, normal)
        for i in range(count):
            if ring:
                angle = 2 * np.pi * i / count
                offset = ring_radius(kind) * (np.cos(angle) * normal + np.sin(angle) * binormal)
            else:
                offset = normal * kind["strand_mm"] * (i - (count - 1) / 2)
            strands[i].append(p + offset)
    return [np.array(s) for s in strands]


def bundles(all_runs: list[Run], types: dict) -> list[tuple[str, np.ndarray, np.ndarray, float, list[str]]]:
    """Rigid segments shared by >= SLEEVE_MIN_RUNS runs or of a run marked ``sleeve``: (body, a, b, bundle
    diameter, runs)."""
    shared = {}
    for run in all_runs:
        for a, b in run.segments():
            if a.body != b.body or a.name.endswith("+") or b.name.endswith("+"):
                continue
            key = (a.body, tuple(sorted((a.name, b.name))))
            entry = shared.setdefault(key, [a.xyz, b.xyz, [], [], False])
            entry[2].append(run_diameter(run, types))
            entry[3].append(run.name)
            entry[4] = entry[4] or run.sleeve
    return [
        (key[0], a, b, bundle_diameter(diameters), names)
        for key, (a, b, diameters, names, forced) in sorted(shared.items())
        if forced or len(names) >= SLEEVE_MIN_RUNS
    ]


def _digest(assembly: list[Instance]) -> str:
    digest = hashlib.sha256(SOURCE.read_bytes() + ELECTRONICS.read_bytes())
    for module in ("wiring.py", "wiring_anchors.py", "wiring_router.py"):
        digest.update((HERE / module).read_bytes())
    for item in assembly:
        digest.update(item.id.encode() + mesh_stamp(item.mesh) + item.matrix.tobytes())
    return digest.hexdigest()[:12]


def instances(assembly: list[Instance]) -> list[Instance]:
    """Cable, sleeve, tie and tie-mount instances for the assembled robot (cached in build/cad/wiring)."""
    data = load()
    digest = _digest(assembly)
    manifest_path = CACHE / "manifest.json"
    if manifest_path.is_file() and json.loads(manifest_path.read_text())["digest"] == digest:
        entries = json.loads(manifest_path.read_text())["instances"]
    else:
        CACHE.mkdir(parents=True, exist_ok=True)
        entries = _build(routed(assembly, data), data)
        manifest_path.write_text(json.dumps({"digest": digest, "instances": entries}, indent=1))
    return [
        Instance(e["id"], e["part"], CACHE / e["mesh"], np.array(e["matrix"]), e["body"], e["kind"], e["meta"])
        for e in entries
    ]


def tie_points(all_runs: list[Run], types: dict) -> list[tuple[Point, np.ndarray, float]]:
    """Every node with a cable tie: (node, bundle direction, bundle diameter through it)."""
    through = {}
    for run in all_runs:
        for k, point in enumerate(run.points):
            if not point.tie or "splice" in point.tie:
                continue
            direction = run.points[min(k + 1, len(run.points) - 1)].xyz - run.points[max(k - 1, 0)].xyz
            direction = direction / max(np.linalg.norm(direction), 1e-9)
            entry = through.setdefault(point.name, [point, np.zeros(3), []])
            entry[1] += direction if np.dot(entry[1], direction) >= 0 else -direction
            entry[2].append(run_diameter(run, types))
    return [(p, d / max(np.linalg.norm(d), 1e-9), bundle_diameter(ds)) for p, d, ds in through.values()]


def _build(all_runs: list[Run], data: dict) -> list[dict]:
    types = data["cable_types"]
    entries = []

    def add(ident, part, mesh, body, kind, meta, matrix=None):
        name = ident.replace("/", "_").replace("#", "_") + ".stl"
        mesh.export(CACHE / name)
        matrix = np.eye(4) if matrix is None else matrix
        entries.append(
            {
                "id": ident,
                "part": part,
                "mesh": name,
                "body": body,
                "kind": kind,
                "matrix": matrix.tolist(),
                "meta": {"module": "wiring", **meta},
            }
        )

    for run in all_runs:
        kind = types[run.type]
        for index, (body, flexible, points) in enumerate(polyline(run)):
            length = length_mm(points)
            for strand_index, (colour, strand) in enumerate(zip(kind["colours"], conductors(points, kind))):
                meta = {
                    "cable": run.cable,
                    "run": run.name,
                    "type": run.type,
                    "colour": colour,
                    "flex": flexible,
                    "length_mm": round(length, 1),
                    "mass_kg": kind["kg_per_m"] / len(kind["colours"]) * length / 1000,
                }
                add(
                    f"cable/{run.name}#{index}.{strand_index}",
                    f"cable/{run.type}",
                    tube(strand, kind["od_mm"] / 2),
                    body,
                    "cable",
                    meta,
                )
    for index, (body, a, b, diameter, names) in enumerate(bundles(all_runs, types)):
        length = float(np.linalg.norm(b - a))
        meta = {
            "type": "spiral_wrap",
            "colour": "sleeve",
            "flex": False,
            "runs": names,
            "length_mm": round(length, 1),
            "mass_kg": data["sleeve_kg_per_m"] * length / 1000,
        }
        add(
            f"cable/sleeve#{index}",
            "cable/spiral_wrap",
            tube(np.array([a, b]), diameter / 2 + data["sleeve_wall_mm"]),
            body,
            "cable",
            meta,
        )
    for index, (point, direction, diameter) in enumerate(tie_points(all_runs, types)):
        ring = trimesh.creation.torus(diameter / 2 + TIE_THICKNESS_MM, TIE_THICKNESS_MM / 2)
        ring.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], direction))
        ring.apply_translation(point.xyz)
        meta = {
            "type": "cable_tie",
            "colour": "tie",
            "flex": False,
            "node": point.name,
            "holds": point.tie,
            "mass_kg": TIE_MASS_KG,
        }
        add(f"cable/tie#{index}", "cable/cable_tie", ring, point.body, "cable", meta)
    return entries
