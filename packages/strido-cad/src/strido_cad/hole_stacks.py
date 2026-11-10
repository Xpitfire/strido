"""Find every fastener axis of the upstream mechanics from coaxial holes (B-rep).

Each group of coaxial small holes (radius 0.9..1.9 mm: M2 .. M3 clearance/pilot)
across the upstream printed solids is one bolted joint. For each group we report
the solids it passes through with their spans along the axis, the hole radius in
each (clearance >= 1.5 mm, pilot/self-tap < 1.5 mm), counterbores (r 2.6..3.4)
and whether a modelled screw from the upstream STEP sits on it.

Output: build/verify/hole_stacks.json (consumed by `strido_cad.fasteners`).
"""

import json

import numpy as np
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer

from .features import cylinders
from .paths import HOLE_STACKS_JSON, UPSTREAM_STEP
from .step_tree import read_step_leaves

STEP = UPSTREAM_STEP
OUT = HOLE_STACKS_JSON
AXIS_TOL_MM = 0.35
SKIP = (
    "raspberry",
    "rpi4",
    "pca9685",
    "turnigy",
    "ubec",
    "spacer",
    "servo holder3",
    "rodend",
    "short rod",
    "socket button",
)


def solids(shape):
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        yield explorer.Current()
        explorer.Next()


def _axial(hole, group):
    """Span of a hole along the group axis, measured from the group reference point."""
    sign = 1.0 if np.dot(np.array(hole["axis"]), group["axis"]) > 0 else -1.0
    shift = float(np.dot(np.array(hole["point"]) - group["point"], group["axis"]))
    a, b = (shift + sign * hole["span"][0], shift + sign * hole["span"][1])
    return min(a, b), max(a, b)


def main():
    holes = []
    screws = []
    for leaf in read_step_leaves(STEP):
        lowered = leaf.path_str.lower()
        if any(token in lowered for token in SKIP):
            continue
        if "m3 screw" in leaf.name.lower():
            for cylinder in cylinders(leaf.shape):
                if 1.3 < cylinder.radius_mm < 1.6 and not cylinder.is_hole:
                    screws.append(
                        {
                            "path": leaf.path_str,
                            "point": cylinder.axis_point_mm.tolist(),
                            "axis": cylinder.axis_direction.tolist(),
                            "span": list(cylinder.span_mm),
                        }
                    )
                    break
            continue
        for index, solid in enumerate(solids(leaf.shape)):
            for cylinder in cylinders(solid):
                if not cylinder.is_hole or cylinder.angle_deg < 300:
                    continue
                if 0.9 <= cylinder.radius_mm <= 1.9 or 2.6 <= cylinder.radius_mm <= 3.4:
                    holes.append(
                        {
                            "path": leaf.path_str,
                            "solid": index,
                            "name": leaf.name,
                            "radius": round(cylinder.radius_mm, 3),
                            "point": cylinder.axis_point_mm.tolist(),
                            "axis": cylinder.axis_direction.tolist(),
                            "span": [round(v, 3) for v in cylinder.span_mm],
                        }
                    )
    groups = []
    for hole in holes:
        point, axis = np.array(hole["point"]), np.array(hole["axis"])
        for group in groups:
            if abs(abs(np.dot(axis, group["axis"])) - 1) < 1e-3:
                offset = point - group["point"]
                lateral = offset - np.dot(offset, group["axis"]) * group["axis"]
                if np.linalg.norm(lateral) < AXIS_TOL_MM:
                    group["holes"].append(hole)
                    break
        else:
            groups.append({"point": point, "axis": axis, "holes": [hole]})
    # Split each coaxial line into separate joints where the holes are axially apart.
    split = []
    for group in groups:
        ordered = sorted(group["holes"], key=lambda h: _axial(h, group)[0])
        current = [ordered[0]]
        reach = _axial(ordered[0], group)[1]
        for hole in ordered[1:]:
            start, end = _axial(hole, group)
            if start > reach + 3.0:
                split.append({"point": group["point"], "axis": group["axis"], "holes": current})
                current = []
                reach = end
            current.append(hole)
            reach = max(reach, end)
        split.append({"point": group["point"], "axis": group["axis"], "holes": current})
    groups = split
    report = []
    for group in groups:
        small = [h for h in group["holes"] if h["radius"] <= 1.9]
        if not small:
            continue
        spans = [_axial(h, group) for h in group["holes"]]
        modelled = [
            s
            for s in screws
            if abs(abs(np.dot(np.array(s["axis"]), group["axis"])) - 1) < 1e-3
            and np.linalg.norm(
                (np.array(s["point"]) - group["point"])
                - np.dot(np.array(s["point"]) - group["point"], group["axis"]) * group["axis"]
            )
            < AXIS_TOL_MM
        ]
        report.append(
            {
                "point": group["point"].round(3).tolist(),
                "axis": group["axis"].round(4).tolist(),
                "extent": [min(s[0] for s in spans), max(s[1] for s in spans)],
                "parts": sorted(
                    {
                        (h["path"].split("/")[-1] if "=>[" not in h["path"] else h["path"].split("/")[-2])
                        for h in group["holes"]
                    }
                ),
                "holes": group["holes"],
                "modelled_screws": modelled,
            }
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1))
    print(f"{len(holes)} holes -> {len(report)} fastener axes; {len(screws)} modelled screws")


if __name__ == "__main__":
    main()
