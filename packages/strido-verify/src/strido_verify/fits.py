"""Fit and tolerance check of every screw joint and bearing seat in the printed parts.

For each screw of the assembled robot (reference pose) the shank axis is sampled every
0.5 mm. At each sample every printed part around the axis is cut with the plane normal
to the axis; the cut tells whether the axis runs through material, a hole, or nothing,
and the hole's inscribed diameter. Per (screw, part) the narrowest diameter decides the fit:

* clearance       hole >= d + 0.05 (warn below d + 0.20: chase with the drill in the report)
* thread-forming  printed pilot (CAD hole - expected shrink) 0.70 d .. 0.90 d ok, up to 0.93 d warn
                  (weak grip), with >= 1.5 d engaged length (only the part of the span that is
                  narrower than d counts; 1.0 .. 1.5 d warns)
* FAIL            line-to-line holes (d .. d + 0.05), pilots outside the band, a screw through
                  solid material, a too short thread-forming engagement, clearance > d + 1.6
                  under a head or nut. On nut joints a hole narrower than clearance is a
                  "tight passage" warning (drill to clearance). Upstream holes listed in
                  `accepted_deviations` (with an ADR and a builder action) are warnings.

Every screw must also end in something that holds it: a coaxial nut, a thread-forming
printed part, or a threaded vendor part / stand-off. Every bearing must sit in a printed
seat: seats are cut at the bearing mid-plane and compared with the bearing outer diameter
(press-fit band); a bearing without a seat fails.

Limits: hardware/verification/tolerances.yaml. Writes docs/verification/data/fits.json and
docs/verification/fits.md; exit 1 on any failure.
"""

import json
import sys
from collections import Counter
from dataclasses import asdict
from typing import Any

import numpy as np
import trimesh

from strido.workspace import path
from strido_cad import assembly, catalog
from strido_cad.assembly import Instance
from strido_cad.fastener_meshes import CATALOGUE

from .fit_geometry import (
    LIMITS,
    AxialItem,
    Coaxial,
    SeatFit,
    aabb_hits,
    bearing_axis,
    coaxial_spans,
    measure_seats,
    section_state,
)
from .fits_model import PartFit, ScrewFit
from .fits_report import write_markdown

REPORT_JSON = path("docs/verification/data/fits.json")
THREADED_KINDS = {"nut", "standoff", "insert"}

__all__ = ["Coaxial", "PartFit", "ScrewFit", "classify", "terminate"]


# --------------------------------------------------------------------------- classification


def classify(hole_d: float, nominal: float) -> tuple[str, str, str]:
    """(fit, status, note) of a hole the screw passes through or threads into."""
    clearance, forming = LIMITS["screw_clearance"], LIMITS["thread_forming"]
    over = hole_d - nominal
    if over >= clearance["fail_below_over_nominal_mm"]:
        if over < clearance["warn_below_over_nominal_mm"]:
            return "clearance", "warn", "tight after printing: chase with a drill"
        return "clearance", "ok", ""
    if over >= 0.0:
        return "line-to-line", "fail", "neither clearance nor thread-forming: drill to clearance"
    printed_ratio = (hole_d - LIMITS["process"]["expected_hole_shrink_mm"]) / nominal
    if printed_ratio < forming["min_ratio"]:
        return (
            "thread-forming",
            "fail",
            f"pilot {hole_d:.2f} mm too small (printed ratio {printed_ratio:.2f}): part may split",
        )
    if printed_ratio > forming["warn_max_ratio"]:
        return "thread-forming", "fail", f"pilot {hole_d:.2f} mm too large (printed ratio {printed_ratio:.2f}): no grip"
    if printed_ratio > forming["ok_max_ratio"]:
        return (
            "thread-forming",
            "warn",
            f"weak grip (printed ratio {printed_ratio:.2f}): stop when snug; if it spins, harden the pilot with thin CA glue and re-drive (no anaerobic thread locker on plastic)",
        )
    return "thread-forming", "ok", ""


def screw_axis(instance: Instance) -> tuple[np.ndarray, np.ndarray]:
    """Head bearing point and unit axis (canonical fastener frame: head at z=0, shank along +z)."""
    axis = instance.matrix[:3, 2] / np.linalg.norm(instance.matrix[:3, 2])
    return instance.matrix[:3, 3].copy(), axis


def part_fit(
    part_instance: Instance,
    depths: np.ndarray,
    states: list[tuple[str, float]],
    thread: dict[str, float],
    coaxial: list[Coaxial],
    step: float,
) -> PartFit | None:
    inside = [(t, state, d) for t, (state, d) in zip(depths, states, strict=True) if state != "outside"]
    span = len(inside) * step
    if span < LIMITS["sampling"]["min_span_mm"]:
        return None
    nominal, head_d = float(thread["d"]), float(thread["dk"])
    start, end = float(inside[0][0]), float(inside[-1][0])
    solid_depths = [t for t, state, _ in inside if state == "solid"]
    hole_d = min((d for _, state, d in inside if state == "hole"), default=0.0)
    engaged = sum(step for _, state, d in inside if state == "hole" and d < nominal)
    name = part_instance.part.split("/")[1]
    source = part_instance.meta.get("source", "")

    def result(fit: str, status: str, note: str = "") -> PartFit:
        return PartFit(
            name,
            part_instance.id,
            source,
            round(start, 2),
            round(span, 2),
            round(hole_d, 3),
            fit,
            status,
            note,
            round(engaged, 2),
        )

    if solid_depths:
        holes_before = [t for t, state, _ in inside if state == "hole" and t < solid_depths[0]]
        if holes_before:
            return result(
                "solid", "fail", f"pilot ends {end - solid_depths[0] + step:.1f} mm before the screw tip: deepen it"
            )
        return result("solid", "fail", "screw axis runs through solid material: no hole in the printed part")
    bearing_cover = sum(max(0.0, min(end, c.end) - max(start, c.start)) for c in coaxial if c.kind == "bearing")
    if bearing_cover >= 0.8 * (end - start):
        return result("bearing bore", "ok", "screw runs inside bearings/bushings held by this part")
    clearance = LIMITS["screw_clearance"]
    if hole_d - nominal > clearance["fail_above_over_nominal_mm"]:
        bears_head = start <= 1.0 and hole_d < head_d + 0.2  # a hole wider than the head is an access bore
        bears_nut = any(c.kind == "nut" and abs(c.start - end) <= 1.0 for c in coaxial)
        if bears_head or bears_nut:
            return result(
                "oversize", "fail", f"hole {hole_d:.2f} mm leaves the {'head' if bears_head else 'nut'} unsupported"
            )
        return result("passage", "ok", "screw (or its head) crosses a bore or cavity of this part")
    fit, status, note = classify(hole_d, nominal)
    if status == "fail":
        status, note = accepted(name, fit, hole_d, nominal, status, note)
    return result(fit, status, note)


def accepted(part: str, fit: str, hole_d: float, nominal: float, status: str, note: str) -> tuple[str, str]:
    """Explicitly accepted deviations of upstream parts (tolerances.yaml `accepted_deviations`, ADR-009)."""
    for deviation in LIMITS["accepted_deviations"]:
        matches = part in deviation["parts"] and fit == deviation["fit"] and nominal == deviation["nominal_mm"]
        if matches and deviation["min_hole_mm"] <= hole_d <= deviation["max_hole_mm"]:
            return "warn", f"accepted deviation ({deviation['adr']}): {deviation['action']}"
    return status, note


def measure_screw(
    instance: Instance,
    printed: list[tuple[Instance, trimesh.Trimesh]],
    vendor: list[tuple[Instance, np.ndarray]],
    coaxial_items: list[AxialItem],
) -> ScrewFit:
    spec = instance.part.split("/")[1]
    item = CATALOGUE["items"][spec]
    thread = CATALOGUE["thread"][item["thread"]]
    nominal, length = float(thread["d"]), float(item["length"])
    head, axis = screw_axis(instance)
    tip = head + axis * length
    sampling = LIMITS["sampling"]
    depths = np.arange(sampling["edge_margin_mm"], length - sampling["edge_margin_mm"] + 1e-9, sampling["step_mm"])
    coaxial = coaxial_spans(head, axis, length, coaxial_items)
    parts = []
    for part_instance, mesh in printed:
        if not aabb_hits(mesh.bounds, head, tip, nominal):
            continue
        states = [section_state(mesh, head + axis * t, axis) for t in depths]
        fit = part_fit(part_instance, depths, states, thread, coaxial, sampling["step_mm"])
        if fit is not None:
            parts.append(fit)
    parts.sort(key=lambda p: p.start_mm)
    termination = terminate(parts, coaxial, nominal, tip, vendor)
    statuses = [p.status for p in parts]
    status = "fail" if "fail" in statuses or termination == "none" else "warn" if "warn" in statuses else "ok"
    return ScrewFit(instance.id, spec, item["thread"], instance.meta.get("joint", ""), termination, status, parts)


def terminate(
    parts: list[PartFit],
    coaxial: list[Coaxial],
    nominal: float,
    tip: np.ndarray,
    vendor: list[tuple[Instance, np.ndarray]],
) -> str:
    """What holds the screw; re-grades narrow holes on nut joints and the terminal engagement.

    On a nut joint every printed hole is meant as a clearance hole: one narrower than clearance
    (a thread-forming-sized or line-to-line hole) is drilled to the clearance size in the report
    before assembly, a defined builder action (warn), never a thread the joint relies on."""
    forming = LIMITS["thread_forming"]
    if any(c.kind in ("nut", "standoff") for c in coaxial):
        for part in parts:
            if part.fit in ("thread-forming", "line-to-line"):
                part.fit, part.status, part.note = (
                    "tight passage",
                    "warn",
                    "narrow hole on a nut joint: drill to clearance",
                )
        return "nut"
    threaded = [p for p in parts if p.fit == "thread-forming"]
    if threaded:
        last = threaded[-1]
        engaged = last.engaged_mm / nominal
        if engaged < forming["warn_engagement_diameters"]:
            short = f"engagement {last.engaged_mm:.1f} mm < {forming['warn_engagement_diameters']} d"
            last.note = f"{last.note}; {short}" if last.status == "fail" and last.note else short
            last.status = "fail"
        elif engaged < forming["min_engagement_diameters"] and last.status == "ok":
            last.status, last.note = (
                "warn",
                f"short engagement {last.engaged_mm:.1f} mm (< {forming['min_engagement_diameters']} d)",
            )
        return "thread-forming"
    if any(np.all(bounds[0] - 0.5 <= tip) and np.all(tip <= bounds[1] + 0.5) for _, bounds in vendor):
        return "vendor thread"
    return "none"


def axial_items(instances: list[Instance]) -> list[AxialItem]:
    """Nuts and stand-offs (canonical fastener frame) and bearings (axis from their mesh)."""
    items = []
    for instance in instances:
        name = instance.part.split("/")[1]
        if instance.kind == "fastener":
            entry = CATALOGUE["items"][name]
            if entry["kind"] not in THREADED_KINDS:
                continue
            thread = CATALOGUE["thread"][entry["thread"]]
            length = float(entry.get("length", thread["h"] if entry["standard"] == "din985" else thread["m"]))
            axis = instance.matrix[:3, 2] / np.linalg.norm(instance.matrix[:3, 2])
            items.append(
                AxialItem("nut" if entry["kind"] == "nut" else "standoff", instance.matrix[:3, 3].copy(), axis, length)
            )
        elif name in LIMITS["bearings"]:
            width = float(LIMITS["bearings"][name]["width"])
            centre, axis = bearing_axis(assembly.world_mesh(instance), float(LIMITS["bearings"][name]["od"]))
            items.append(AxialItem("bearing", centre, axis, width))
    return items


def run() -> tuple[list[ScrewFit], list[SeatFit]]:
    instances = catalog.full_assembly()
    printed = [(i, assembly.world_mesh(i)) for i in instances if i.kind == "printed"]
    screws = [
        i for i in instances if i.kind == "fastener" and CATALOGUE["items"][i.part.split("/")[1]]["kind"] == "screw"
    ]
    vendor = [  # threaded vendor parts; bearings and sleeves never hold a screw
        (i, assembly.world_mesh(i).bounds)
        for i in instances
        if i.kind == "purchased" and i.part.split("/")[1] not in LIMITS["bearings"]
    ]
    bearings = [(i, assembly.world_mesh(i)) for i in instances if i.part.split("/")[1] in LIMITS["bearings"]]
    items = axial_items(instances)
    return [measure_screw(s, printed, vendor, items) for s in screws], measure_seats(bearings, printed)


def main() -> None:
    screws, seats = run()
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    document: dict[str, Any] = {"screws": [asdict(s) for s in screws], "seats": [asdict(s) for s in seats]}
    REPORT_JSON.write_text(json.dumps(document, indent=1))
    write_markdown(screws, seats)
    counts = Counter(s.status for s in screws)
    seat_fail = sum(s.status == "fail" for s in seats)
    print(
        f"screws: {len(screws)} ok={counts['ok']} warn={counts['warn']} fail={counts['fail']}; seats: {len(seats)} fail={seat_fail}"
    )
    if counts["fail"] or seat_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
