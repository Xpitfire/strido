"""Wiring gate: every cable of hardware/wiring.yaml as routed through the CAD by strido_cad.wiring.

Checks (docs/verification/wiring.md; exit 1 on any fail):

* reach: a ready-made cable (servo lead, USB, ribbon, STEMMA QT, Dupont, the pack's lead) covers its
  routed path plus its terminations; the excess is reported (fold it and tie it);
* stock: cut-to-length wire per BOM line and colour (routed + terminations + slack) fits what is bought,
  and there are enough ready-made cables;
* loops: a lead crossing a hip joint has a free loop of at least `LOOP_SLACK` x the longest distance
  between its two ties over the hip range of hardware/joint_limits.yaml;
* ports: one cable per WAGO port, one plug per PCA9685 channel;
* clearance: no rigid run passes through a part of its own body; against every part of another body it
  keeps the running clearance of hardware/verification/tolerances.yaml in every operating pose.

Not modelled: bend radii (route corners are sharp; the cable takes a wider curve) and the shape of a hip
loop (its ends and length are checked, not where it hangs).

Clearance is measured against surface samples of the meshes (`SURFACE_MM` spacing), independent of the
router's voxel grid.
"""

import itertools
import json
import sys
from dataclasses import asdict, dataclass

import numpy as np
import trimesh
import yaml
from scipy.spatial import cKDTree

from strido.workspace import path
from strido_cad import assembly, catalog, wiring, wiring_geometry
from strido_cad.paths import JOINT_LIMITS

from .poses import operating_poses
from .wiring_report import render

LIMITS = yaml.safe_load(path("hardware/verification/tolerances.yaml").read_text())["moving_clearance"]
BOM = path("hardware/bom.yaml")
REPORT_JSON = path("docs/verification/data/wiring.json")
REPORT_MD = path("docs/verification/wiring.md")
LOOP_SLACK = 1.2  # the free loop is 20 % longer than the farthest its ties get apart
REACH_MARGIN_MM = 10.0  # ready-made leads vary; keep this much spare
HIP_SAMPLES = 46
SAMPLE_MM = 0.25  # cable centreline sampling
SURFACE_MM = 0.5  # mesh surface sampling (crossing a surface puts a centreline sample within ~0.4 mm)
SURFACE_HIT_MM = 0.45
PENETRATION_MM = 0.5  # a cable pressed against a part may flatten this much
ANCHOR_RELIEF_MM = 1.0  # beyond the straight lead-out, the cable leaves the connector body


@dataclass
class Finding:
    check: str
    item: str
    status: str  # ok | warn | fail
    value: str
    limit: str
    note: str = ""


def _samples(points: np.ndarray, step: float = SAMPLE_MM) -> np.ndarray:
    out = [points[0]]
    for a, b in itertools.pairwise(points):
        count = max(1, int(np.ceil(np.linalg.norm(b - a) / step)))
        out.extend(a + (b - a) * t for t in np.linspace(0.0, 1.0, count + 1)[1:])
    return np.array(out)


def _trees(instances) -> dict[str, tuple[cKDTree, np.ndarray, list[str]]]:
    """Per rigid body: KD-tree of surface samples (CAD pose), owner index per sample, owner part types."""
    points, owners, names = {}, {}, {}
    for item in instances:
        if item.kind in ("reference", "cable"):
            continue
        mesh = assembly.world_mesh(item)
        vertices, _ = trimesh.remesh.subdivide_to_size(mesh.vertices, mesh.faces, max_edge=SURFACE_MM)
        names.setdefault(item.body, []).append(item.part.split("/")[1])
        points.setdefault(item.body, []).append(vertices)
        owners.setdefault(item.body, []).append(np.full(len(vertices), len(names[item.body]) - 1))
    return {b: (cKDTree(np.concatenate(points[b])), np.concatenate(owners[b]), names[b]) for b in points}


def _is_anchor(name: str, data: dict) -> bool:
    return ":" in name or name in data["anchors"]


def _relief(run: wiring.Run, data: dict) -> tuple[float, float]:
    """Centreline length at each end that sits in its connector's lead-out (not clearance-checked)."""
    stubs = data["anchor_stub_mm"]

    def stub(point: wiring.Point) -> float:
        if not _is_anchor(point.name, data):
            return 0.0
        kind = point.name.split(":")[0] if ":" in point.name else "default"
        return stubs.get(kind, stubs["default"]) + ANCHOR_RELIEF_MM

    return stub(run.points[0]), stub(run.points[-1])


def _pieces(run: wiring.Run, data: dict):
    """Rigid pieces as drawn: (body, centreline samples of each conductor) with the anchor lead-outs removed."""
    kind = data["cable_types"][run.type]
    head, tail = _relief(run, data)
    pieces = wiring_geometry.polyline(run)
    for index, (body, flexible, points) in enumerate(pieces):
        if flexible:
            continue
        strands = wiring_geometry.conductors(points, kind)
        for strand in strands:
            samples = _samples(strand)
            distance = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(samples, axis=0), axis=1))])
            keep = np.ones(len(samples), dtype=bool)
            if index == 0:
                keep &= distance >= head
            if index == len(pieces) - 1:
                keep &= distance <= distance[-1] - tail
            if keep.any():
                yield body, samples[keep]


def check_clearance(runs, data, trees) -> list[Finding]:
    types = data["cable_types"]
    findings = []
    poses = operating_poses()
    transforms = {name: assembly.body_transforms(pose) for name, pose in poses.items()}
    inverse = {name: {b: np.linalg.inv(m) for b, m in t.items()} for name, t in transforms.items()}
    for run in runs:
        kind = types[run.type]
        radius = kind["od_mm"] / 2  # per drawn conductor
        worst_static, worst_moving = (np.inf, ""), (np.inf, "", "")
        for body, samples in _pieces(run, data):
            tree, owner, names = trees[body]
            distance, index = tree.query(samples)
            limit = np.maximum(SURFACE_HIT_MM, radius - PENETRATION_MM)
            depth = distance - limit
            k = int(np.argmin(depth))
            if depth[k] < worst_static[0]:
                worst_static = (float(depth[k]), names[owner[index[k]]])
            for pose_name, pose_transforms in transforms.items():
                world = samples @ pose_transforms[body][:3, :3].T + pose_transforms[body][:3, 3]
                for other, (other_tree, other_owner, other_names) in trees.items():
                    if other == body:
                        continue
                    matrix = inverse[pose_name][other]
                    bound = radius + LIMITS["warn_below_mm"] + 1.0  # farther samples cannot change the verdict
                    gap, hit = other_tree.query(world @ matrix[:3, :3].T + matrix[:3, 3], distance_upper_bound=bound)
                    if not np.isfinite(gap).any():
                        continue
                    gap = gap - radius
                    j = int(np.argmin(gap))
                    if gap[j] < worst_moving[0]:
                        worst_moving = (float(gap[j]), other_names[other_owner[hit[j]]], pose_name)
        status = "fail" if worst_static[0] < 0 else "ok"
        findings.append(
            Finding(
                "through parts", run.name, status, f"{worst_static[0]:+.2f} mm", "≥ 0", f"nearest: {worst_static[1]}"
            )
        )
        if np.isfinite(worst_moving[0]):
            gap = worst_moving[0]
            status = "fail" if gap < LIMITS["fail_below_mm"] else "warn" if gap < LIMITS["warn_below_mm"] else "ok"
            findings.append(
                Finding(
                    "moving parts",
                    run.name,
                    status,
                    f"{gap:.2f} mm",
                    f"≥ {LIMITS['warn_below_mm']} mm",
                    f"{worst_moving[1]} ({worst_moving[2]})",
                )
            )
    return findings


def check_loops(raw_runs) -> list[Finding]:
    limits = yaml.safe_load(JOINT_LIMITS.read_text())["limits"]
    stand = wiring.stand_pose()
    findings, seen = [], set()
    for run in raw_runs:
        for a, b in run.segments():
            if a.body == b.body or (a.name, b.name) in seen:
                continue
            seen.add((a.name, b.name))
            moving, fixed = (a, b) if a.body != "base" else (b, a)
            leg = moving.body.split(".")[0]
            low, high = limits[leg]["hip_deg"]
            chords = []
            for degrees in np.linspace(low, high, HIP_SAMPLES):
                pose = {**stand, leg: (np.radians(degrees), stand[leg][1], stand[leg][2])}
                matrix = assembly.body_transforms(pose)[moving.body]
                chords.append(float(np.linalg.norm(matrix[:3, :3] @ moving.xyz + matrix[:3, 3] - fixed.xyz)))
            loop = a.loop_mm if a.loop_mm is not None else b.loop_mm
            need = LOOP_SLACK * max(chords)
            findings.append(
                Finding(
                    "hip loop",
                    f"{a.name} → {b.name}",
                    "ok" if loop >= need else "fail",
                    f"{loop:.0f} mm",
                    f"≥ {need:.1f} mm",
                    f"tie-to-tie {min(chords):.1f}–{max(chords):.1f} mm over the hip range",
                )
            )
    return findings


def run_length(run: wiring.Run) -> float:
    total = 0.0
    for a, b in run.segments():
        total += np.linalg.norm(b.xyz - a.xyz) if a.body == b.body else (a.loop_mm or b.loop_mm)
    return float(total)


def _end(name: str, data: dict) -> str:
    kind = name.split(":")[0] if ":" in name else None
    return {"servo": "plug", "pca": "crimp", "wago": "wago"}.get(kind) or data["anchors"][name]["end"]


def lengths(runs, data) -> list[dict]:
    """Per run: routed length, terminations, and the cut length for cut-to-length wire."""
    rows = []
    for run in runs:
        kind = data["cable_types"][run.type]
        ends = [p.name for p in (run.points[0], run.points[-1]) if _is_anchor(p.name, data)]
        routed = run_length(run)
        terminations = sum(data["termination_mm"][_end(e, data)] for e in ends)
        slack = max(data["slack"]["min_mm"], data["slack"]["fraction"] * routed)
        rows.append(
            {
                "run": run.name,
                "cable": run.cable,
                "type": run.type,
                "from": run.points[0].name,
                "to": run.points[-1].name,
                "routed_mm": round(routed, 1),
                "terminations_mm": terminations,
                # ready-made cables keep their length; everything else is cut (from stock, or a servo lead's branch)
                "cut_mm": None
                if "supplied_mm" in kind or kind.get("ready_made")
                else round(routed + terminations + slack),
            }
        )
    return rows


def _branch_need(branch: dict) -> float:
    """Length a branch takes from the lead past the split: its cut length, or its route if it is not cut."""
    if branch.get("cut_mm") is not None:
        return branch["cut_mm"]
    return branch["routed_mm"] + branch["terminations_mm"]


def check_reach(rows, data) -> list[Finding]:
    types = data["cable_types"]
    by_cable = {}
    for row in rows:
        by_cable.setdefault(row["cable"], []).append(row)
    findings = []
    for cable, parts in by_cable.items():
        trunk = next((p for p in parts if p["run"] == cable), None)
        if trunk is None:  # separate cores (the pack lead): each core on its own
            paths = [(p["type"], p["routed_mm"] + p["terminations_mm"]) for p in parts]
        else:  # a lead and its branches: the trunk plus the longest branch as cut (slack included)
            branches = [p for p in parts if p is not trunk] or [{"routed_mm": 0.0, "terminations_mm": 0.0}]
            paths = [(trunk["type"], trunk["routed_mm"] + trunk["terminations_mm"] + _branch_need(b)) for b in branches]
        kind, need = max(paths, key=lambda p: p[1])
        supplied = types[kind].get("supplied_mm")
        if supplied is None:
            if types[kind].get("ready_made"):  # supplied with a part, length not published
                findings.append(
                    Finding("reach", cable, "warn", f"{need:.0f} mm", "length not published", types[kind]["source"])
                )
            continue
        status = "ok" if need <= supplied - REACH_MARGIN_MM else "fail"
        findings.append(
            Finding(
                "reach",
                cable,
                status,
                f"{need:.0f} mm",
                f"≤ {supplied - REACH_MARGIN_MM:.0f} mm",
                f"{supplied} mm supplied, {supplied - need:.0f} mm to fold and tie",
            )
        )
    return findings


def check_stock(rows, runs, data) -> list[Finding]:
    types = data["cable_types"]
    bom = {line["id"]: line for line in yaml.safe_load(BOM.read_text())["lines"]}
    used = {}
    for row in rows:
        kind = types[row["type"]]
        if row["cut_mm"] is not None and "bom" in kind:
            for colour in kind["colours"]:
                used[(kind["bom"], colour)] = used.get((kind["bom"], colour), 0) + row["cut_mm"]
    findings = []
    for (line, colour), total in sorted(used.items()):
        stock = data["stock_per_unit_mm"][line][colour] * bom[line]["qty"]
        status = "ok" if total <= stock else "fail"
        findings.append(
            Finding("wire stock", f"{line} {colour}", status, f"{total} mm", f"≤ {stock} mm", bom[line]["name"])
        )
    sleeve_mm = sum(float(np.linalg.norm(b - a)) for _, a, b, _, _ in wiring_geometry.bundles(runs, types))
    have = data["stock_per_unit_mm"]["spiral_wrap"]["black"] * bom["spiral_wrap"]["qty"]
    findings.append(
        Finding(
            "wire stock",
            "spiral_wrap",
            "ok" if sleeve_mm <= have else "fail",
            f"{sleeve_mm:.0f} mm",
            f"≤ {have} mm",
            bom["spiral_wrap"]["name"],
        )
    )
    ties = len(wiring_geometry.tie_points(runs, types))
    have = bom["cable_ties"]["qty"] * data["pieces_per_unit"]["cable_ties"]
    findings.append(
        Finding(
            "ready-made cables",
            "cable_ties",
            "ok" if ties <= have else "fail",
            str(ties),
            f"≤ {have}",
            bom["cable_ties"]["name"],
        )
    )
    counts = {}
    for run in runs:
        kind = types[run.type]
        if "supplied_mm" in kind and "bom" in kind and run.name == run.cable:
            counts[kind["bom"]] = counts.get(kind["bom"], 0) + kind.get("pieces", 1)
    for line, count in sorted(counts.items()):
        have = bom[line]["qty"] * data["pieces_per_unit"].get(line, 1)
        findings.append(
            Finding(
                "ready-made cables", line, "ok" if count <= have else "fail", str(count), f"≤ {have}", bom[line]["name"]
            )
        )
    return findings


def check_ports(runs) -> list[Finding]:
    users = {}
    for run in runs:
        for point in (run.points[0], run.points[-1]):
            if point.name.startswith("pca:"):
                users.setdefault(point.name, []).append(run.name)
            elif point.name.startswith("wago:"):  # a pair anchor uses the port on both rails
                side, bay, port, *rail = point.name.removeprefix("wago:").split(".")
                for name_rail in rail or ("V+", "GND"):
                    users.setdefault(f"wago:{side}.{bay}.{port}.{name_rail}", []).append(run.name)
    findings = []
    for port, names in sorted(users.items()):
        findings.append(
            Finding("port", port, "ok" if len(names) == 1 else "fail", str(len(names)), "1", ", ".join(names))
        )
    return findings


def run_checks() -> tuple[list[Finding], list[dict], dict]:
    data = wiring.load()
    instances = [i for i in catalog.full_assembly() if i.kind != "cable"]
    raw = wiring.runs(instances, data)
    runs = wiring.route_runs(raw, wiring.occupancy(instances), data["cable_types"])
    rows = lengths(runs, data)
    findings = check_reach(rows, data) + check_stock(rows, runs, data) + check_loops(raw) + check_ports(runs)
    findings += check_clearance(runs, data, _trees(instances))
    return findings, rows, data


def main() -> int:
    findings, rows, data = run_checks()
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(
        json.dumps({"findings": [asdict(f) for f in findings], "cut_list": rows}, indent=1, ensure_ascii=False) + "\n"
    )
    REPORT_MD.write_text(render(findings, rows, data))
    failed = [f for f in findings if f.status == "fail"]
    for finding in failed:
        print(f"FAIL {finding.check}: {finding.item} {finding.value} (limit {finding.limit}) {finding.note}")
    print(f"wiring: {len(findings)} checks, {len(failed)} fail, {sum(f.status == 'warn' for f in findings)} warn")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
