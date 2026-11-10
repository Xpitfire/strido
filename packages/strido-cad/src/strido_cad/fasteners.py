"""Derive and verify every upstream fastener from the measured hole stacks.

Matches each coaxial hole stack (build/verify/hole_stacks.json) to exactly one
joint rule in hardware/fasteners_upstream.yaml; unmatched stacks fail the run.
Writes build/verify/fasteners_upstream.json (counts + placements used by the
assembly, renders and BOM).
"""

import itertools
import json
import sys
from collections import Counter

import numpy as np
import yaml

from . import assembly
from .paths import FASTENER_RULES_UPSTREAM, HOLE_STACKS_JSON, UPSTREAM_FASTENERS_JSON

RULES = yaml.safe_load(FASTENER_RULES_UPSTREAM.read_text())
STACKS = HOLE_STACKS_JSON
OUT = UPSTREAM_FASTENERS_JSON
BODY_CENTRE = np.array([-5.0, 20.84, 78.68])


def names_of(stack) -> list[str]:
    names = []
    for hole in stack["holes"]:
        name = hole["name"] if not hole["name"].startswith("=>") else hole["path"].split("/")[-2]
        names.append(name)
    return names


def axis_letter(stack) -> str:
    return "xyz"[int(np.argmax(np.abs(stack["axis"])))]


def matches(rule, stack) -> bool:
    criteria = rule.get("match", rule)  # joints nest their criteria under `match`, ignores are flat
    names = " | ".join(names_of(stack))
    if not all(token in names for token in criteria["parts"]):
        return False
    axis = criteria.get("axis", "any")
    if axis != "any" and axis != axis_letter(stack):
        return False
    low, high = criteria.get("stack_mm", (-1e9, 1e9))
    length = stack["extent"][1] - stack["extent"][0]
    return low <= length <= high


def head_end(rule_head, stack):
    axis = np.array(stack["axis"], dtype=float)
    point = np.array(stack["point"], dtype=float)
    e0, e1 = stack["extent"]
    ends = {"min": (point + axis * e0, axis), "max": (point + axis * e1, -axis)}
    if rule_head in ends:
        return ends[rule_head]
    if rule_head == "counterbore":
        bores = []
        for hole in stack["holes"]:
            if hole["radius"] >= 2.6:
                sign = 1.0 if np.dot(np.array(hole["axis"]), axis) > 0 else -1.0
                shift = float(np.dot(np.array(hole["point"]) - point, axis))
                bores.append(sorted((shift + sign * hole["span"][0], shift + sign * hole["span"][1])))
        # The head pocket is the longest wide bore that opens at an end of the stack (a servo
        # spline cavity at the other end is wide too, but short).
        open_bores = [b for b in bores if min(abs(b[0] - e0), abs(b[1] - e1)) <= 0.5]
        if open_bores:
            lo, hi = max(open_bores, key=lambda b: b[1] - b[0])
            if abs(lo - e0) < abs(hi - e1):  # pocket at the min end: bearing face at its floor
                return point + axis * hi, axis
            return point + axis * lo, -axis
    # outer: the end farther from the body centre; inner: the nearer end
    a, b = point + axis * e0, point + axis * e1
    a_is_outer = np.linalg.norm(a - BODY_CENTRE) >= np.linalg.norm(b - BODY_CENTRE)
    if (rule_head == "outer") == a_is_outer:
        return a, axis
    return b, -axis


def nut_seat(stack, head, direction, mode="pocket"):
    """Nut bearing face and body direction: in the axial gap nearest the tip (captive pocket,
    seated on the head-side wall), else - or with mode "tip" - on the outer face at the tip end."""
    axis = np.array(stack["axis"], dtype=float)
    point = np.array(stack["point"], dtype=float)
    spans = []
    for hole in stack["holes"]:
        sign = 1.0 if np.dot(np.array(hole["axis"]), axis) > 0 else -1.0
        shift = float(np.dot(np.array(hole["point"]) - point, axis))
        spans.append(sorted((shift + sign * hole["span"][0], shift + sign * hole["span"][1])))
    spans.sort()
    gaps = [(a[1], b[0]) for a, b in itertools.pairwise(spans) if b[0] - a[1] >= 2.2]
    toward_tip = float(np.dot(direction, axis))  # +1: tip at larger axial values
    if gaps and mode == "pocket":
        gap = max(gaps, key=lambda g: g[0] * toward_tip)  # the gap closest to the tip
        face = gap[0] if toward_tip > 0 else gap[1]  # tightening pulls the nut onto the head-side wall
        return point + axis * face, direction
    tip = stack["extent"][1] if toward_tip > 0 else stack["extent"][0]
    return point + axis * tip, direction


def merge_split_stacks(stacks):
    """Joints with `merge_mm` (count_override) register as several coaxial stacks per fastener
    (e.g. the two tibia halves of one pin). Merge stacks on one axis line whose extents are
    closer than merge_mm into one stack, so head and nut land on the real outer ends."""
    merged, used = [], set()
    for index, stack in enumerate(stacks):
        if index in used:
            continue
        rule = next((r for r in RULES["joints"] if matches(r, stack)), None)
        window = RULES["count_override"].get(rule["id"], {}).get("merge_mm") if rule else None
        if window is None:
            merged.append(stack)
            continue
        group = dict(
            stack, holes=list(stack["holes"]), extent=list(stack["extent"]), rule_id=rule["id"]
        )  # merged length no longer matches stack_mm
        axis, point = np.array(stack["axis"], dtype=float), np.array(stack["point"], dtype=float)
        for other_index in range(index + 1, len(stacks)):
            other = stacks[other_index]
            if other_index in used or next((r for r in RULES["joints"] if matches(r, other)), None) is not rule:
                continue
            other_axis = np.array(other["axis"], dtype=float)
            offset = np.array(other["point"], dtype=float) - point
            if (
                abs(abs(np.dot(other_axis, axis)) - 1) > 1e-3
                or np.linalg.norm(offset - np.dot(offset, axis) * axis) > 0.5
            ):
                continue
            shift = float(np.dot(offset, axis))
            sign = 1.0 if np.dot(other_axis, axis) > 0 else -1.0
            lo, hi = sorted((shift + sign * other["extent"][0], shift + sign * other["extent"][1]))
            if lo - group["extent"][1] > window or group["extent"][0] - hi > window:
                continue
            group["extent"] = [min(group["extent"][0], lo), max(group["extent"][1], hi)]
            group["holes"] += other["holes"]
            used.add(other_index)
        merged.append(group)
    return merged


def dedupe(placements):
    """Split stacks of one joint produce coaxial duplicates; keep one per axis position.

    Two placements are duplicates when they have the same spec and joint, lie on the same
    axis line and their heads are closer than 12 mm.
    """
    kept = []
    for entry in placements:
        head, axis = np.array(entry["head"]), np.array(entry["axis"])
        window = 12.0
        duplicate = any(
            other["spec"] == entry["spec"]
            and other["joint"] == entry["joint"]
            and abs(abs(np.dot(np.array(other["axis"]), axis)) - 1) < 1e-3
            and np.linalg.norm((np.array(other["head"]) - head) - np.dot(np.array(other["head"]) - head, axis) * axis)
            < 0.5
            and abs(np.dot(np.array(other["head"]) - head, axis)) < window
            for other in kept
        )
        if not duplicate:
            kept.append(entry)
    return kept


def assign_bracket_screws(placements) -> None:
    """Per leg, the two leg-servo screws nearest the top bracket fix the bracket and are longer."""
    brackets = {
        item.body: assembly.world_mesh(item).bounds.mean(axis=0)
        for item in assembly.upstream_instances()
        if item.part == "printed/servo_mount_top_bracket"
    }
    extra = next(item for item in RULES["extra"] if item["id"] == "bracket_screws")
    per_leg = extra["qty"] // len(brackets)
    for body, centre in brackets.items():
        candidates = [p for p in placements if p["joint"] == "leg_servo_ears_and_bracket" and p["body"] == body]
        candidates.sort(key=lambda p: np.linalg.norm(np.array(p["head"]) - centre))
        for placement in candidates[:per_leg]:
            placement["spec"] = extra["per_item"][0]["spec"]
            placement["joint"] = "bracket_screws"


def body_of(stack, head_point) -> str:
    best, distance = "base", 1e9
    for hole in stack["holes"]:
        leg = assembly._leg_of(hole["path"])
        hole_point = np.array(hole["point"]) + np.array(hole["axis"]) * np.mean(hole["span"])
        d = np.linalg.norm(hole_point - head_point)
        if d < distance:
            distance = d
            best = assembly._leg_body(hole["path"], leg) if leg else "base"
    return best


def apply_corrections(placements) -> None:
    """Rotate the fasteners of corrected joints with their parts (hardware/assembly/corrections.yaml)."""
    for correction, per_leg in assembly.correction_matrices():
        for placement in placements:
            matrix = per_leg.get(placement["body"].split(".")[0])
            if matrix is None or placement["joint"] not in correction["fastener_joints"]:
                continue
            placement["head"] = (matrix @ np.append(placement["head"], 1.0))[:3].tolist()
            placement["axis"] = (matrix[:3, :3] @ np.array(placement["axis"])).tolist()
            placement["correction"] = correction["id"]


def main():
    raw_stacks = json.loads(STACKS.read_text())
    stacks = merge_split_stacks(raw_stacks)
    matched = Counter()
    placements = []
    unmatched = []
    for stack in stacks:
        if any(matches(rule, stack) for rule in RULES["ignore"]):
            continue
        if "rule_id" in stack:
            rule = next(rule for rule in RULES["joints"] if rule["id"] == stack["rule_id"])
        else:
            rule = next((rule for rule in RULES["joints"] if matches(rule, stack)), None)
        if rule is None:
            unmatched.append(stack)
            continue
        matched[rule["id"]] += 1
        head, direction = head_end(rule["head"], stack)
        body = body_of(stack, head)
        heads = [(head, direction)]
        if rule["id"] == "knee_axle":  # second knee screw from the other side
            axis = np.array(stack["axis"], dtype=float)
            other = np.array(stack["point"]) + axis * (
                stack["extent"][0] if np.allclose(direction, -axis) else stack["extent"][1]
            )
            heads.append((other, -direction))
        specs = [item["spec"] for item in rule["per_stack"] for _ in range(item["qty"])]
        screws = [spec for spec in specs if "iso4762" in spec or "iso7380" in spec]
        washers = [spec for spec in specs if "iso7089" in spec]
        nuts = [spec for spec in specs if "iso4032" in spec or "din985" in spec]
        for index, spec in enumerate(screws):
            point, axis_dir = heads[min(index, len(heads) - 1)]
            if index < len(washers):  # washer on the part surface, screw head on the washer
                placements.append(
                    {
                        "spec": washers[index],
                        "head": point.tolist(),
                        "axis": (-axis_dir).tolist(),
                        "body": body,
                        "joint": rule["id"],
                    }
                )
                point = point - axis_dir * 0.5
            placements.append(
                {"spec": spec, "head": point.tolist(), "axis": axis_dir.tolist(), "body": body, "joint": rule["id"]}
            )
        for spec in nuts:
            point, axis_dir = nut_seat(stack, head, direction, rule.get("nut", "pocket"))
            placements.append(
                {"spec": spec, "head": point.tolist(), "axis": axis_dir.tolist(), "body": body, "joint": rule["id"]}
            )
    placements = dedupe(placements)
    assign_bracket_screws(placements)
    apply_corrections(placements)
    counts = Counter(p["spec"] for p in placements)
    # Gate: the placed fasteners (what CAD, manual and BOM use) must equal the rule totals.
    expected = Counter()
    for rule in RULES["joints"]:
        stacks_used = RULES["count_override"].get(rule["id"], {}).get("stacks", matched[rule["id"]])
        for item in rule["per_stack"]:
            expected[item["spec"]] += stacks_used * item["qty"]
    for extra in RULES["extra"]:
        for item in extra["per_item"]:
            expected[item["spec"]] += extra["qty"] * item["qty"]
    for extra in RULES["extra"]:  # extras that re-specify fasteners already counted by a joint rule
        if "replaces" in extra:
            expected[extra["replaces"]] -= extra["qty"]
    if counts != expected:
        print(
            f"PLACEMENT/COUNT MISMATCH: placed {dict(sorted(counts.items()))} expected {dict(sorted(expected.items()))}"
        )
        sys.exit(1)
    report = {
        "matched_stacks": dict(matched),
        "fastener_counts": dict(sorted(counts.items())),
        "placements": placements,
        "unmatched": [
            {
                "parts": names_of(s),
                "axis": axis_letter(s),
                "stack_mm": round(s["extent"][1] - s["extent"][0], 2),
                "point": s["point"],
            }
            for s in unmatched
        ],
    }
    OUT.write_text(json.dumps(report, indent=1))
    for key, value in report["matched_stacks"].items():
        print(f"  {key:30s} {value}")
    print(f"counts: {report['fastener_counts']}")
    if unmatched:
        print(f"UNMATCHED {len(unmatched)} stacks:")
        for item in report["unmatched"]:
            print(f"    {item}")
        sys.exit(1)


if __name__ == "__main__":
    main()
