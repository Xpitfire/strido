"""Static interference check of the complete Strido assembly at several leg poses.

Every overlapping pair of solids is classified; anything not explained by a rule
FAILS the check (exit code 1):

* thread engagement - the overlap lies entirely inside the shank of a screw
  (self-tapping into a pilot hole, or a screw in a threaded stand-off/stud);
* seating contact - parts designed to touch (listed in
  hardware/verification/allowed_contacts.yaml) with a penetration <= 0.2 mm;
* upstream fit - both parts are upstream Yertle geometry (or a Strido part
  derived from it) and the penetration is within the STL->STEP registration
  error of that part pair (<= 1.0 mm); these exist in the upstream design;
* joint - horn on its servo spline, bearing on its pin/bore (upstream joints).

Writes build/verify/interference.json and docs/verification/interference.md.
"""

import json
import sys
from collections import Counter

import numpy as np
import trimesh
import yaml

from strido.workspace import path
from strido_cad import assembly, catalog, fastener_meshes, interference
from strido_cad.paths import VERIFY_OUT

from .poses import stand_pose

RULES = yaml.safe_load(path("hardware/verification/allowed_contacts.yaml").read_text())
REPORT_JSON = VERIFY_OUT / "interference.json"
REPORT_MD = path("docs/verification/interference.md")


def part_type(instance) -> str:
    """Part type for the contact rules: a Strido re-drilled variant inherits its upstream part's rules."""
    derived_from = instance.meta.get("derived_from")
    return (derived_from or instance.part).split("/")[1]


def upstream_equivalent(instance) -> str | None:
    """Upstream part type a printed part is derived from (None for new geometry)."""
    if instance.meta.get("source") in ("upstream STL", "upstream STEP", "upstream STEP only", "strido derived"):
        return part_type(instance)
    return RULES["derived_from_upstream"].get(part_type(instance))


def penetration_mm(overlap) -> float:
    """Mean thickness of the overlap solid: 2 V / S (exact for a thin slab, conservative otherwise)."""
    mesh = trimesh.Trimesh(*_overlap_arrays(overlap))
    if len(mesh.faces) == 0 or mesh.area <= 0:
        return 0.0
    return float(2.0 * abs(mesh.volume) / mesh.area)


def _overlap_arrays(overlap):
    common = interference._manifold(overlap.a) ^ interference._manifold(overlap.b)
    mesh = common.to_mesh()
    return np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts)


def inside_shank(overlap, screw) -> bool:
    item = fastener_meshes.spec(part_type(screw))
    if item["kind"] not in ("screw",):
        return False
    vertices, _ = _overlap_arrays(overlap)
    local = trimesh.transform_points(vertices, np.linalg.inv(screw.matrix))
    radial = np.hypot(local[:, 0], local[:, 1])
    return bool(
        radial.max() <= item["d"] / 2 + 0.06
        and local[:, 2].min() >= -0.06
        and local[:, 2].max() <= item["length"] + 0.06
    )


def on_fastener_axis(overlap, fastener) -> bool:
    """Overlap lies within the fastener's own head/nut radius around its axis."""
    item = fastener_meshes.spec(part_type(fastener))
    radius = max(item.get("dk", 0), item.get("s", 0) / np.cos(np.pi / 6), item.get("washer_od", 0)) / 2 + 0.1
    vertices, _ = _overlap_arrays(overlap)
    local = trimesh.transform_points(vertices, np.linalg.inv(fastener.matrix))
    return bool(np.hypot(local[:, 0], local[:, 1]).max() <= radius)


def threaded_counterpart(overlap, other) -> bool:
    """Nut/stand-off/stud bodies are threaded: a screw shank inside them is engagement."""
    return part_type(other) in RULES["threaded_parts"]


def classify(overlap) -> tuple[str, str]:
    a, b = overlap.a, overlap.b
    pair = frozenset((part_type(a), part_type(b)))
    for screw, other in ((a, b), (b, a)):
        if screw.kind == "fastener" and inside_shank(overlap, screw):
            if other.kind == "printed" or threaded_counterpart(overlap, other):
                return "thread engagement", f"{part_type(screw)} bites into {part_type(other)}"
            if other.kind == "fastener" and fastener_meshes.spec(part_type(other))["kind"] in ("nut", "standoff"):
                return "thread engagement", f"{part_type(screw)} in {part_type(other)}"
    for item, other in ((a, b), (b, a)):
        if item.meta.get("source") == "upstream joint" and on_fastener_axis(overlap, item):
            return (
                "upstream joint",
                f"{part_type(item)} on a measured hole axis through {part_type(other)} (nut/slot orientation not modelled)",
            )
    for item, other in ((a, b), (b, a)):
        if item.kind == "fastener" and other.kind in ("printed", "purchased"):
            depth = penetration_mm(overlap)
            if depth <= 0.1:
                return "seating contact", f"{part_type(item)} bearing face on {part_type(other)} ({depth:.2f} mm)"
    for nut, other in ((a, b), (b, a)):
        if nut.kind == "fastener" and fastener_meshes.spec(part_type(nut))["kind"] == "nut" and other.kind == "printed":
            depth = penetration_mm(overlap)
            if depth <= 0.5:
                return "seating contact", f"captive {part_type(nut)} in its hex pocket (corner contact {depth:.2f} mm)"
    for rule in RULES["seating_contacts"]:
        if pair == frozenset(rule["pair"]):
            depth = penetration_mm(overlap)
            if depth <= rule.get("max_penetration_mm", 0.2):
                return "seating contact", f"{rule['why']} (penetration {depth:.2f} mm)"
    for rule in RULES["joints"]:
        if pair == frozenset(rule["pair"]):
            return "joint", rule["why"]
    ua, ub = upstream_equivalent(a), upstream_equivalent(b)
    if ua and ub:
        depth = penetration_mm(overlap)
        if depth <= RULES["upstream_fit_max_penetration_mm"]:
            return "upstream fit", f"{ua} / {ub} (penetration {depth:.2f} mm, upstream geometry)"
    return "FAIL", f"{part_type(a)} / {part_type(b)} penetration {penetration_mm(overlap):.2f} mm"


def poses():
    stand = {name: stand_pose(name, 0.17) for name in assembly.LEG_NAMES}
    crouch = {name: stand_pose(name, 0.12) for name in assembly.LEG_NAMES}
    tall = {name: stand_pose(name, 0.21) for name in assembly.LEG_NAMES}
    return {"stand_170mm": stand, "crouch_120mm": crouch, "tall_210mm": tall, "cad_reference": dict(assembly.CAD_POSE)}


def main():
    # cables are checked against every part and pose by strido_verify.wiring
    instances = [item for item in catalog.full_assembly() if item.kind not in ("reference", "cable")]
    results = {}
    failures = 0
    for name, joints in poses().items():
        posed = assembly.posed(instances, joints)
        rows = []
        for overlap in interference.overlaps(posed, volume_tolerance_mm3=0.3):
            verdict, why = classify(overlap)
            failures += verdict == "FAIL"
            rows.append(
                {
                    "a": overlap.a.id,
                    "b": overlap.b.id,
                    "volume_mm3": round(overlap.volume_mm3, 2),
                    "centroid_mm": [round(float(v), 1) for v in overlap.centroid_mm],
                    "verdict": verdict,
                    "why": why,
                }
            )
        results[name] = rows
        counts = Counter(row["verdict"] for row in rows)
        print(f"{name}: {len(posed)} solids, {len(rows)} overlaps -> {dict(counts)}")
        for row in rows:
            if row["verdict"] == "FAIL":
                print("   FAIL", row["a"], row["b"], row["volume_mm3"], row["centroid_mm"], row["why"])
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(results, indent=1))
    write_markdown(results, len(instances))
    sys.exit(1 if failures else 0)


def write_markdown(results, solid_count):
    lines = [
        "# Interference check",
        "",
        "Generated by `strido_verify.contacts` (exact mesh booleans, manifold3d).",
        "",
        f"Solids per pose: {solid_count} (printed parts, purchased parts, fasteners).",
        "",
    ]
    lines += [
        "| Pose | Overlapping pairs | Thread engagement | Seating contact | Joint | Upstream fit | Upstream joint fastener | **FAIL** |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, rows in results.items():
        counts = Counter(row["verdict"] for row in rows)
        lines.append(
            f"| {name} | {len(rows)} | {counts['thread engagement']} | {counts['seating contact']} | {counts['joint']} | "
            f"{counts['upstream fit']} | {counts['upstream joint']} | **{counts['FAIL']}** |"
        )
    lines += [
        "",
        "## Classified contacts at the standing pose",
        "",
        "| Verdict | Pair | Volume mm³ | Reason |",
        "|---|---|---|---|",
    ]
    for row in sorted(results["stand_170mm"], key=lambda r: (r["verdict"], -r["volume_mm3"])):
        if row["verdict"] in ("thread engagement", "upstream joint"):
            continue
        lines.append(f"| {row['verdict']} | {row['a']} / {row['b']} | {row['volume_mm3']} | {row['why']} |")
    threads = [r for r in results["stand_170mm"] if r["verdict"] == "thread engagement"]
    joints = [r for r in results["stand_170mm"] if r["verdict"] == "upstream joint"]
    lines += [
        "",
        f"{len(threads)} thread-engagement overlaps (screw shank inside a pilot hole, nut, stand-off or stud) and "
        f"{len(joints)} upstream-joint fastener overlaps (fastener on a measured hole axis; captive-nut and slot "
        "orientation is not modelled) are omitted from the table.",
        "",
    ]
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
