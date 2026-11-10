"""Read-only queries over the tracked Strido hardware data and the last verification run.

Every answer comes from a tracked file (hardware/*.yaml, docs/catalog/parts.json,
docs/verification/data/*.json); nothing here runs the CAD pipeline except `measure_gap`.
The functions return plain JSON-serialisable dicts so the CLI, the MCP server and the
tests share one contract.
"""

import json
from pathlib import Path
from typing import Any

import yaml

from strido.workspace import repo_root

PARTS_JSON = "docs/catalog/parts.json"
FITS_JSON = "docs/verification/data/fits.json"
CLEARANCE_JSON = "docs/verification/data/clearance.json"
GENERATED_BY = {
    PARTS_JSON: "make catalog",
    FITS_JSON: "make verify (strido_verify.fits)",
    CLEARANCE_JSON: "make verify (strido_verify.clearance)",
}
LEG_NAMES = ("FL", "FR", "RL", "RR")
VERIFICATION_REPORTS = ("interference", "clearance", "fits", "sensors", "electronics", "printability")


class MissingArtefactError(FileNotFoundError):
    """A generated artefact the query needs has not been built yet."""


def _root() -> Path:
    return repo_root()


def _yaml(relative: str) -> Any:
    return yaml.safe_load((_root() / relative).read_text())


def _json(relative: str) -> Any:
    target = _root() / relative
    if not target.is_file():
        raise MissingArtefactError(f"{relative} is missing: run `{GENERATED_BY.get(relative, 'make publish')}`")
    return json.loads(target.read_text())


def _parts() -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = _json(PARTS_JSON)["parts"]
    return parts


def list_parts(kind: str = "all") -> list[dict[str, Any]]:
    """Every catalogue part (printed | purchased | fastener | all): id, title, quantity, size."""
    if kind not in {"all", "printed", "purchased", "fastener"}:
        raise ValueError(f"unknown kind {kind!r}: use printed, purchased, fastener or all")
    fields = ("id", "kind", "title", "qty", "bbox_mm")
    return [{k: p.get(k) for k in fields} for p in _parts() if kind in ("all", p["kind"])]


def get_part(part_id: str) -> dict[str, Any]:
    """Full catalogue entry of one part plus the fits it takes part in."""
    matches = [p for p in _parts() if p["id"] == part_id]
    if not matches:
        known = sorted(p["id"] for p in _parts() if part_id.split("_")[0] in p["id"])[:10]
        raise KeyError(f"unknown part {part_id!r}; similar: {known}")
    entry = dict(matches[0])
    entry["fits"] = fits_for_part(part_id)
    return entry


def get_fastener(spec: str) -> dict[str, Any]:
    """Nominal dimensions of a catalogue fastener and the joints that use it."""
    catalogue = _yaml("hardware/fasteners.yaml")
    if spec not in catalogue["items"]:
        raise KeyError(f"unknown fastener {spec!r}; known: {sorted(catalogue['items'])}")
    item = dict(catalogue["items"][spec])
    item["thread_dimensions_mm"] = catalogue["thread"][item["thread"]]
    item["standard_title"] = catalogue["standards"][item["standard"]]["title"]
    part = next((p for p in _parts() if p["id"] == spec), None)
    item["qty_in_robot"] = part["qty"] if part else 0
    return {"spec": spec, **item}


def fits_for_part(part_id: str) -> list[dict[str, Any]]:
    """Screw fits measured in a printed part (empty for vendor parts or before `make verify`)."""
    try:
        screws = _json(FITS_JSON)["screws"]
    except MissingArtefactError:
        return []
    rows = []
    for screw in screws:
        for part in screw["parts"]:
            if part["part"] == part_id:
                rows.append(
                    {
                        "screw": screw["spec"],
                        "joint": screw["joint"],
                        "fit": part["fit"],
                        "hole_d_mm": part["hole_d_mm"],
                        "span_mm": part["span_mm"],
                        "status": part["status"],
                    }
                )
    return rows


def fits_summary(status: str = "fail") -> dict[str, Any]:
    """Screw-fit counts and the screws with the given status (ok | warn | fail)."""
    document = _json(FITS_JSON)
    screws = document["screws"]
    counts = {s: sum(1 for screw in screws if screw["status"] == s) for s in ("ok", "warn", "fail")}
    selected = [screw for screw in screws if screw["status"] == status]
    seats = document["seats"]
    return {
        "counts": counts,
        "bearing_seats": {"total": len(seats), "fail": sum(s["status"] == "fail" for s in seats)},
        "screws": selected[:50],
        "truncated": len(selected) > 50,
    }


def clearance_pairs(max_gap_mm: float = 1.0) -> dict[str, Any]:
    """Pairs of moving parts whose minimum gap over all operating poses is below `max_gap_mm`."""
    document = _json(CLEARANCE_JSON)
    pairs = [p for p in document["pairs"] if p["gap_mm"] < max_gap_mm]
    return {"poses": document["poses"], "joint_interfaces": document["joint_interfaces"], "pairs": pairs}


def joint_limits(leg: str) -> dict[str, Any]:
    """Collision- and linkage-safe joint limits of one leg (degrees), from the ROM sweep."""
    if leg not in LEG_NAMES:
        raise KeyError(f"unknown leg {leg!r}; use one of {LEG_NAMES}")
    document = _yaml("hardware/joint_limits.yaml")
    return {
        "leg": leg,
        "limits_deg": document["limits"][leg],
        "servo_half_travel_deg": document["servo_half_travel_deg"],
    }


def pinout(query: str = "") -> dict[str, Any]:
    """Controller pins, I²C devices and servo channels; `query` filters by pad, function or device text."""
    model = _yaml("hardware/electronics.yaml")
    pads = model["controller"]["pads"]
    needle = query.lower()
    pins = [
        {**pin, "gpio": pads[pin["pad"]]}
        for pin in model["controller"]["pins"]
        if not needle or needle in json.dumps(pin).lower()
    ]
    devices = [
        {**d, "address": f"0x{d['address']:02X}"}
        for d in model["i2c"]["devices"]
        if not needle or needle in json.dumps(d).lower()
    ]
    channels = model["servos"]["channels"]
    if needle:
        channels = {
            leg: joints
            for leg, joints in channels.items()
            if needle in leg.lower() or needle in "servo channel pca9685"
        }
    return {"pins": pins, "i2c": devices, "servo_channels": channels}


def bom_line(line_id: str) -> dict[str, Any]:
    """One BOM line with every offer, or the list of line ids when `line_id` is empty."""
    bom = _yaml("hardware/bom.yaml")
    if not line_id:
        return {"lines": [{"id": line["id"], "name": line["name"], "qty": line["qty"]} for line in bom["lines"]]}
    for line in bom["lines"]:
        if line["id"] == line_id:
            offers = [
                {**offer, "vendor_name": bom["vendors"][offer["vendor"]]["name"]} for offer in line.get("offers", [])
            ]
            return {**line, "offers": offers}
    raise KeyError(f"unknown BOM line {line_id!r}")


def verification_status() -> dict[str, Any]:
    """Headline of every generated verification report (first summary paragraph)."""
    reports = {}
    for name in VERIFICATION_REPORTS:
        report = _root() / "docs/verification" / f"{name}.md"
        if not report.is_file():
            reports[name] = "missing: run make verify"
            continue
        paragraphs = [block.strip() for block in report.read_text().split("\n\n") if block.strip()]
        summary = next((p for p in paragraphs[1:] if not p.startswith(("#", "|", "Generated"))), paragraphs[-1])
        reports[name] = summary.replace("\n", " ")[:400]
    return reports


def measure_gap(part_a: str, part_b: str, pose: str = "stand_170mm") -> dict[str, Any]:
    """Exact minimum distance between two parts in a named operating pose (loads the CAD: slow on a cold cache)."""
    from strido_cad import assembly, catalog, interference
    from strido_verify.poses import operating_poses

    poses = operating_poses()
    if pose not in poses:
        raise KeyError(f"unknown pose {pose!r}; known: {sorted(poses)}")
    placed = assembly.posed([i for i in catalog.full_assembly() if i.kind != "reference"], poses[pose])
    group_a = [i for i in placed if i.part.split("/")[1] == part_a]
    group_b = [i for i in placed if i.part.split("/")[1] == part_b]
    if not group_a or not group_b:
        raise KeyError(f"part not in the assembly: {part_a if not group_a else part_b}")
    search_mm = 50.0
    if part_a == part_b:  # two instances of one part type (e.g. the left and right feet)
        candidates, between = group_a, lambda a, b: a.id != b.id
    else:
        ids_a = {i.id for i in group_a}
        candidates, between = group_a + group_b, lambda a, b: (a.id in ids_a) != (b.id in ids_a)
    gaps = interference.gaps(candidates, search_mm, between)
    if not gaps:
        return {"pose": pose, "min_gap_mm": None, "note": f"farther apart than {search_mm} mm"}
    nearest = min(gaps, key=lambda g: g.gap_mm)
    return {"pose": pose, "min_gap_mm": round(nearest.gap_mm, 3), "a": nearest.a.id, "b": nearest.b.id}
