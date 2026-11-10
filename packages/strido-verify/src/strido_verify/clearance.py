"""Running clearance between parts that move relative to each other, over every operating pose.

The interference check proves nothing overlaps; this check proves moving parts do not
*rub*: printed parts deviate ~0.2 mm per surface, so two surfaces of different rigid
bodies (e.g. calf and thigh, femur and shoulder frame, a screw head and a passing link)
need a real gap in every pose the robot goes through.

* Pairs already touching at the CAD reference pose across a joint of the leg (bearing in its
  bore, pin in a link, horn on a spline) are the joint interfaces themselves and are not
  gated. Only bodies joined by a revolute joint or linkage pin qualify (`JOINTED_BODIES`);
  any other touching cross-body pair is gated like every moving pair.
* Pairs whose gap stays constant in every pose (within `constant_gap_band_mm`) turn about a
  shared axis (bearing face beside a link, washer under a pin): listed as rotational interfaces.
* Every other pair of instances on different bodies sweeps past each other and must keep
  >= `fail_below_mm` in all operating poses (stand/crouch/tall, eight trot phases, hips out/in);
  below `warn_below_mm` it is reported as tight.

Limits: hardware/verification/tolerances.yaml (`moving_clearance`). Writes
docs/verification/data/clearance.json and docs/verification/clearance.md; exit 1 on failure.
"""

import json
import sys
from collections import defaultdict
from typing import Any

import yaml

from strido.workspace import path
from strido_cad import assembly, catalog, interference
from strido_cad.assembly import Instance

from .poses import operating_poses

LIMITS = yaml.safe_load(path("hardware/verification/tolerances.yaml").read_text())["moving_clearance"]
REPORT_JSON = path("docs/verification/data/clearance.json")
REPORT_MD = path("docs/verification/clearance.md")
# Body types joined by a revolute joint or a linkage pin of one leg (base-hip: hip servo axis).
JOINTED_BODIES = {
    frozenset(pair)
    for pair in (
        ("base", "hip"),
        ("hip", "thigh"),
        ("thigh", "calf"),
        ("hip", "arm"),
        ("arm", "short_link"),
        ("crank", "short_link"),
        ("crank", "thigh"),
        ("crank", "long_link"),
        ("calf", "long_link"),
    )
}


def part_type(instance: Instance) -> str:
    return instance.part.split("/")[1]


def different_bodies(a: Instance, b: Instance) -> bool:
    return a.body != b.body and "reference" not in (a.kind, b.kind)


def pair_key(a: Instance, b: Instance) -> tuple[str, str]:
    return (a.id, b.id) if a.id < b.id else (b.id, a.id)


def jointed(a: Instance, b: Instance) -> bool:
    """Bodies of the same leg (or base and a hip) connected by one joint or linkage pin."""
    leg_a, _, type_a = a.body.rpartition(".")
    leg_b, _, type_b = b.body.rpartition(".")
    same_leg = leg_a == leg_b or "" in (leg_a, leg_b)
    return same_leg and frozenset((type_a, type_b)) in JOINTED_BODIES


def joint_interfaces(instances: list[Instance]) -> set[tuple[str, str]]:
    """Cross-body pairs in contact at the CAD reference pose across a joint (the joints themselves)."""
    touching = interference.gaps(
        instances, LIMITS["interface_contact_mm"], lambda a, b: different_bodies(a, b) and jointed(a, b)
    )
    return {pair_key(g.a, g.b) for g in touching}


def run() -> dict[str, Any]:
    # cables are checked against every part and pose by strido_verify.wiring
    instances = [i for i in catalog.full_assembly() if i.kind not in ("reference", "cable")]
    interfaces = joint_interfaces(instances)
    search = LIMITS["warn_below_mm"] + 0.5
    poses = operating_poses()
    seen: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(list)
    labels: dict[tuple[str, str], dict[str, Any]] = {}
    for pose_name, pose in poses.items():
        placed = assembly.posed(instances, pose)
        for gap in interference.gaps(
            placed, search, lambda a, b: different_bodies(a, b) and pair_key(a, b) not in interfaces
        ):
            key = pair_key(gap.a, gap.b)
            seen[key].append((pose_name, gap.gap_mm))
            labels[key] = {
                "a": key[0],
                "b": key[1],
                "parts": sorted((part_type(gap.a), part_type(gap.b))),
                "bodies": sorted((gap.a.body, gap.b.body)),
            }
    pairs = []
    for key, samples in seen.items():
        gaps = [g for _, g in samples]
        pose_name, minimum = min(samples, key=lambda s: s[1])
        constant = len(samples) == len(poses) and max(gaps) - minimum <= LIMITS["constant_gap_band_mm"]
        if constant:
            status = "interface"
        else:
            status = (
                "fail" if minimum < LIMITS["fail_below_mm"] else "warn" if minimum < LIMITS["warn_below_mm"] else "ok"
            )
        pairs.append(
            {
                **labels[key],
                "gap_mm": round(minimum, 3),
                "gap_max_mm": round(max(gaps), 3),
                "pose": pose_name,
                "status": status,
            }
        )
    return {
        "poses": list(poses),
        "joint_interfaces": len(interfaces),
        "pairs": sorted(pairs, key=lambda e: e["gap_mm"]),
    }


def write_markdown(report: dict[str, Any]) -> None:
    pairs = report["pairs"]
    by_status: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in pairs:
        by_status[entry["status"]].append(entry)
    lines = [
        "# Moving-part clearance",
        "",
        "Generated by `strido_verify.clearance` (exact minimum distance between closed meshes, manifold3d).",
        "",
        f"Poses: {', '.join(report['poses'])}.",
        "",
        f"Pairs on different rigid bodies closer than {LIMITS['warn_below_mm'] + 0.5:.1f} mm in any pose: {len(pairs)} — "
        f"**fail (< {LIMITS['fail_below_mm']} mm) {len(by_status['fail'])}**, tight (< {LIMITS['warn_below_mm']} mm) "
        f"{len(by_status['warn'])}, ok {len(by_status['ok'])}, rotational interfaces (constant gap) "
        f"{len(by_status['interface'])}. Joint interfaces (in contact at the CAD pose, not gated): "
        f"{report['joint_interfaces']}.",
        "",
        "| Parts | Bodies | Minimum gap (mm) | Maximum gap (mm) | Worst pose | Result |",
        "|---|---|---|---|---|---|",
    ]
    for entry in pairs:
        result = {"fail": "**FAIL**", "warn": "tight", "ok": "ok", "interface": "rotational interface"}[entry["status"]]
        lines.append(
            f"| {' / '.join(entry['parts'])} | {' / '.join(entry['bodies'])} | {entry['gap_mm']:.2f} | "
            f"{entry['gap_max_mm']:.2f} | {entry['pose']} | {result} |"
        )
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines) + "\n")


def main() -> None:
    report = run()
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=1))
    write_markdown(report)
    failed = [e for e in report["pairs"] if e["status"] == "fail"]
    tight = [e for e in report["pairs"] if e["status"] == "warn"]
    for entry in failed:
        print(f"FAIL {entry['parts']} ({entry['bodies']}): {entry['gap_mm']} mm in {entry['pose']}")
    print(
        f"clearance: {len(report['pairs'])} close pairs, {len(failed)} fail, {len(tight)} tight, "
        f"{report['joint_interfaces']} joint interfaces"
    )
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
