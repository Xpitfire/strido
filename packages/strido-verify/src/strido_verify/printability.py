"""Printability of the print kit: every part sliced by a real slicer, plus a wall-thickness scan.

Inputs: the oriented STLs and 3MF plates of `make print` (build/print/print_parts.json lists each
part with its supports and size) and the profile hardware/print/prusaslicer.ini (the print list's
settings). Per part:

* PrusaSlicer slices the STL as it lies on the bed, with supports and a brim exactly as the
  print list prescribes. FAIL: the slicer errors, or reports print stability issues
  (collapsing overhangs, floating bridge anchors, loose extrusions, low bed adhesion) that
  the prescribed supports/brim do not prevent. Filament mass and print time come from the G-code.
* Wall-thickness scan: rays from surface samples into the material. Lateral walls are limited
  by the extrusion width, horizontal skins by the layer height (`printability` in
  hardware/verification/tolerances.yaml); FAIL if a measurable area is thinner than one
  extrusion line / one layer, warn below two lines / three layers.

Every 3MF plate is sliced as arranged (no re-arranging): it must be accepted on the bed.

Writes docs/verification/data/printability.json and docs/verification/printability.md; exit 1 on
any failure. Slicer: STRIDO_PRUSASLICER, else `prusa-slicer` on PATH, else the macOS app bundle.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import trimesh
import yaml
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from strido.workspace import build_dir, path

LIMITS = yaml.safe_load(path("hardware/verification/tolerances.yaml").read_text())["printability"]
PROFILE = path("hardware/print/prusaslicer.ini")
PRINT_JSON = path("build/print/print_parts.json")
PLATES = path("hardware/print/plates")
REPORT_JSON = path("docs/verification/data/printability.json")
REPORT_MD = path("docs/verification/printability.md")
MACOS_PRUSASLICER = "/Applications/PrusaSlicer.app/Contents/MacOS/PrusaSlicer"
SLICE_TIMEOUT_S = 900
WORKERS_MAX = 8
STABILITY_HEADER = "Detected print stability issues"
# Progress lines of the slicer CLI: "<percent> => <stage>"
PROGRESS_LINE = re.compile(r"^\d+ =>")
# G-code summary comments: "; estimated printing time (normal mode) = 1d 2h 3m 4s" -> the duration text
TIME_COMMENT = re.compile(r"^; estimated printing time \(normal mode\) = (.+)$", re.MULTILINE)
# "; total filament used [g] = 12.34" -> the grams
GRAMS_COMMENT = re.compile(r"^; total filament used \[g\] = ([\d.]+)$", re.MULTILINE)
# One duration component such as "2h" or "13m": number and unit
DURATION_PART = re.compile(r"(\d+)([dhms])")
SECONDS_PER_UNIT = {"d": 86400, "h": 3600, "m": 60, "s": 1}
# Stability issues of an unsupported slice that the prescribed supports address (overhangs, bridges)
SUPPORTABLE_ISSUES = {"Collapsing overhang", "Loose extrusions", "Long bridging extrusions", "Floating bridge anchors"}
# "; objects_info = {...}" G-code header (needs gcode_label_objects): the JSON of the printed objects
OBJECTS_INFO = re.compile(r"^; objects_info = (.+)$", re.MULTILINE)
# One object entry in that JSON: its "name" value
OBJECT_NAME = re.compile(r'"name":"([^"]*)"')


@dataclass
class PartResult:
    part: str
    qty: int
    supports: bool
    brim: bool
    status: str  # ok | warn | fail
    slicer_messages: list[str] = field(default_factory=list)
    print_time_s: int = 0
    filament_g: float = 0.0
    thin_lateral_mm2: float = 0.0  # area of lateral walls thinner than the warn limit
    thin_vertical_mm2: float = 0.0
    min_lateral_mm: float = 0.0
    min_vertical_mm: float = 0.0
    notes: list[str] = field(default_factory=list)


def slicer_executable() -> str:
    configured = os.environ.get("STRIDO_PRUSASLICER")
    if configured:
        return configured
    found = shutil.which("prusa-slicer") or (MACOS_PRUSASLICER if Path(MACOS_PRUSASLICER).is_file() else None)
    if found is None:
        raise FileNotFoundError(
            "PrusaSlicer not found: install it (`brew install --cask prusaslicer`) or set STRIDO_PRUSASLICER"
        )
    return found


def slice_file(source: Path, output: Path, extra: list[str]) -> tuple[int, list[str], str]:
    """(exit code, slicer messages without progress lines, G-code text)."""
    command = [
        slicer_executable(),
        "--load",
        str(PROFILE),
        "--export-gcode",
        "--output",
        str(output),
        *extra,
        str(source),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=SLICE_TIMEOUT_S, check=False)
    messages = [
        line.strip()
        for line in (result.stdout + result.stderr).splitlines()
        if line.strip() and not PROGRESS_LINE.match(line) and not line.startswith("Slicing result exported")
    ]
    gcode = output.read_text() if result.returncode == 0 and output.is_file() else ""
    return result.returncode, messages, gcode


def duration_s(text: str) -> int:
    return sum(int(value) * SECONDS_PER_UNIT[unit] for value, unit in DURATION_PART.findall(text))


def thin_wall_area(points: np.ndarray, selected: np.ndarray, area_per_sample: float) -> float:
    """Area of the selected samples that form walls or fins, not short cusp lines.

    Where two surfaces meet at a grazing angle (a hole breaking a face, a fillet ending) the
    thickness falls to zero along a short line: a strip a few tenths wide that the slicer simply
    omits. Samples are clustered (neighbours closer than `cluster_link_mm`); a cluster counts as
    thin material if it is at least `wall_min_width_mm` wide or `fin_min_length_mm` long (a long
    thin rib or knife edge is a real feature, a short cusp is not)."""
    candidates = points[selected]
    if len(candidates) == 0:
        return 0.0
    pairs = cKDTree(candidates).query_pairs(LIMITS["cluster_link_mm"], output_type="ndarray")
    graph = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(len(candidates), len(candidates)))
    count, labels = connected_components(graph, directed=False)
    area = 0.0
    for label in range(count):
        cluster = candidates[labels == label]
        if len(cluster) < 3:
            continue
        centred = cluster - cluster.mean(axis=0)
        axes = np.linalg.svd(centred, full_matrices=False)[2]
        width = float(np.ptp(centred @ axes[1]))  # extent across the cluster's narrow in-surface direction
        length = float(np.ptp(centred @ axes[0]))  # extent along the cluster's long direction
        if width >= LIMITS["wall_min_width_mm"] or length >= LIMITS["fin_min_length_mm"]:
            area += len(cluster) * area_per_sample
    return area


def thickness_scan(mesh: trimesh.Trimesh) -> dict[str, float]:
    """Local material thickness along the inward normal at surface samples (`samples_per_mm2`)."""
    samples = int(min(LIMITS["samples_max"], max(LIMITS["samples_min"], mesh.area * LIMITS["samples_per_mm2"])))
    points, faces = trimesh.sample.sample_surface(mesh, samples, seed=1)
    normals = mesh.face_normals[faces]
    inset_mm = 1e-3  # start just inside the surface so the ray does not hit its own face
    origins = points - normals * inset_mm
    hits, rays, _ = mesh.ray.intersects_location(origins, -normals, multiple_hits=False)
    thickness = np.full(len(points), np.inf)
    # rounded to 0.01 mm: a skin modelled as exactly three layers (0.60 mm) must not read as 0.5999
    thickness[rays] = np.round(np.linalg.norm(hits - origins[rays], axis=1) + inset_mm, 2)
    real = thickness >= LIMITS["coincident_below_mm"]  # zero-thickness hits: duplicate/internal faces of the mesh
    area_per_sample = mesh.area / samples
    lateral = np.abs(normals[:, 2]) < LIMITS["lateral_normal_z_max"]
    walls, skins = LIMITS["lateral_wall_mm"], LIMITS["vertical_skin_mm"]
    return {
        "thin_lateral_mm2": thin_wall_area(points, real & lateral & (thickness < walls["warn_below"]), area_per_sample),
        "thin_vertical_mm2": thin_wall_area(
            points, real & ~lateral & (thickness < skins["warn_below"]), area_per_sample
        ),
        "too_thin_lateral_mm2": thin_wall_area(
            points, real & lateral & (thickness < walls["fail_below"]), area_per_sample
        ),
        "too_thin_vertical_mm2": thin_wall_area(
            points, real & ~lateral & (thickness < skins["fail_below"]), area_per_sample
        ),
        "min_lateral_mm": float(np.percentile(thickness[real & lateral], 1)) if (real & lateral).any() else 0.0,
        "min_vertical_mm": float(np.percentile(thickness[real & ~lateral], 1)) if (real & ~lateral).any() else 0.0,
    }


def stability_issues(messages: list[str]) -> set[str]:
    """Issue names of PrusaSlicer's "Detected print stability issues" block (object names and advice dropped).
    The slicer only runs this analysis for objects printed without supports."""
    if not any(STABILITY_HEADER in m for m in messages):
        return set()
    issues = set()
    for message in messages:
        if STABILITY_HEADER in message or message.endswith((".stl", ".3mf")) or message.startswith("Consider"):
            continue
        issues.update(issue.strip() for issue in message.split(","))
    return issues


def slice_failures(code: int, messages: list[str], gcode: str) -> list[str]:
    """Reasons a slice did not produce a complete print: exit code, no G-code statistics, or any message
    the slicer printed besides the stability block (errors, conflicts, empty print, objects off the bed)."""
    reasons = []
    if code != 0:
        reasons.append(f"slicer exit code {code}")
    if not GRAMS_COMMENT.search(gcode):
        reasons.append("no complete G-code")
    in_stability_block = False
    for message in messages:
        if STABILITY_HEADER in message:
            in_stability_block = True
            continue
        if in_stability_block:
            if message.startswith("Consider"):
                in_stability_block = False
            continue
        reasons.append(f"slicer: {message}")
    return reasons


def check_part(row: dict[str, Any], out: Path) -> PartResult:
    brim = row["bed_mm"][2] > LIMITS["brim_above_height_mm"]
    brim_args = ["--brim-width", str(LIMITS["brim_width_mm"])] if brim else []
    extra = ["--center", "110,110", *brim_args, *(["--support-material"] if row["supports"] else [])]
    code, messages, gcode = slice_file(path(row["file"]), out / f"{row['part']}.gcode", extra)
    result = PartResult(row["part"], row["qty"], row["supports"], brim, "ok", messages)
    failures = slice_failures(code, messages, gcode)
    if row["supports"]:
        if ";TYPE:Support material" not in gcode:  # the print list over-prescribes; the bare run below still judges
            result.notes.append("supports listed, but the slicer finds nothing to support")
        # The stability analysis is skipped for supported objects: run it without supports and keep
        # only the issues supports cannot fix (bed adhesion, floating or fragile parts).
        _, bare_messages, _ = slice_file(
            path(row["file"]), out / f"{row['part']}_bare.gcode", ["--center", "110,110", *brim_args]
        )
        issues = stability_issues(bare_messages) - SUPPORTABLE_ISSUES
    else:
        issues = stability_issues(messages)
    if issues:
        failures.append(f"print stability: {', '.join(sorted(issues))}")
    if failures:
        result.status = "fail"
        result.notes += failures
    times, grams = TIME_COMMENT.findall(gcode), GRAMS_COMMENT.findall(gcode)
    result.print_time_s = duration_s(times[0]) if times else 0
    result.filament_g = float(grams[0]) if grams else 0.0
    scan = thickness_scan(trimesh.load(path(row["file"]), force="mesh"))
    result.thin_lateral_mm2 = round(scan["thin_lateral_mm2"], 1)
    result.thin_vertical_mm2 = round(scan["thin_vertical_mm2"], 1)
    result.min_lateral_mm = round(scan["min_lateral_mm"], 2)
    result.min_vertical_mm = round(scan["min_vertical_mm"], 2)
    area = LIMITS["thin_area_mm2"]
    if scan["too_thin_lateral_mm2"] > area["fail_above"] or scan["too_thin_vertical_mm2"] > area["fail_above"]:
        result.status = "fail"
        result.notes.append("walls, fins or skins thinner than one extrusion line / one layer")
    elif scan["thin_lateral_mm2"] > area["warn_above"] or scan["thin_vertical_mm2"] > area["warn_above"]:
        if result.status == "ok":
            result.status = "warn"
        result.notes.append("thin walls or skins: printable, but only one or two lines / layers thick")
    return result


def check_plate(plate: Path, out: Path) -> dict[str, Any]:
    """Sliced as arranged with supports: every part must be printed, nothing may conflict."""
    code, messages, gcode = slice_file(plate, out / f"{plate.stem}.gcode", ["--dont-arrange", "--support-material"])
    failures = slice_failures(code, messages, gcode)
    with zipfile.ZipFile(plate) as archive:
        expected = archive.read("3D/3dmodel.model").decode().count("<item ")
    printed = OBJECT_NAME.findall(OBJECTS_INFO.search(gcode).group(1)) if OBJECTS_INFO.search(gcode) else []
    if len(printed) != expected:
        failures.append(f"{len(printed)} of {expected} parts printed")
    return {"plate": plate.name, "status": "fail" if failures else "ok", "slicer_messages": failures}


def run() -> dict[str, Any]:
    if not PRINT_JSON.is_file():
        raise FileNotFoundError(f"{PRINT_JSON} is missing: run `make print` first")
    rows = json.loads(PRINT_JSON.read_text())
    out = build_dir("slice")
    workers = min(WORKERS_MAX, os.cpu_count() or 1)
    with ThreadPoolExecutor(workers) as pool:
        parts = list(pool.map(lambda row: check_part(row, out), rows))
        plates = list(pool.map(lambda plate: check_plate(plate, out), sorted(PLATES.glob("*.3mf"))))
    return {
        "slicer": subprocess.run(
            [slicer_executable(), "--help"], capture_output=True, text=True, check=False
        ).stdout.splitlines()[0],
        "profile": str(PROFILE.relative_to(path("."))),
        "parts": [asdict(p) for p in parts],
        "plates": plates,
        "kit_filament_g": round(sum(p.filament_g * p.qty for p in parts), 1),
        "kit_print_time_h": round(sum(p.print_time_s * p.qty for p in parts) / 3600, 1),
    }


def write_markdown(report: dict[str, Any]) -> None:
    parts, plates = report["parts"], report["plates"]
    failed = [p for p in parts if p["status"] == "fail"] + [p for p in plates if p["status"] == "fail"]
    walls, skins = LIMITS["lateral_wall_mm"], LIMITS["vertical_skin_mm"]
    lines = [
        "# Printability",
        "",
        f"Generated by `strido_verify.printability` with {report['slicer']} and `{report['profile']}`.",
        "",
        f"{len(parts)} part types sliced as oriented in the kit, {len(plates)} plates sliced as arranged: "
        f"**{len(failed)} fail**, {sum(p['status'] == 'warn' for p in parts)} warn. Whole kit: "
        f"{report['kit_filament_g']:.0f} g PETG, {report['kit_print_time_h']:.0f} h printing (slicer estimate, all pieces).",
        "",
        f"Thin areas: lateral walls under {walls['warn_below']} mm (two lines) or horizontal skins under "
        f"{skins['warn_below']} mm (three layers); 1 % percentile thickness per orientation.",
        "",
        "| Part | Qty | Supports | Brim | Time | Filament (g) | Thin lateral (mm²) | Thin skin (mm²) | Min wall / skin (mm) | Result | Slicer / notes |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for p in sorted(parts, key=lambda p: ({"fail": 0, "warn": 1, "ok": 2}[p["status"]], p["part"])):
        hours, minutes = divmod(p["print_time_s"] // 60, 60)
        notes = "; ".join(p["notes"] + [m for m in p["slicer_messages"] if not m.endswith(".stl")])
        lines.append(
            f"| {p['part']} | {p['qty']} | {'yes' if p['supports'] else 'no'} | {'yes' if p['brim'] else 'no'} | "
            f"{hours}h {minutes:02d}m | {p['filament_g']:.1f} | {p['thin_lateral_mm2']:.0f} | {p['thin_vertical_mm2']:.0f} | "
            f"{p['min_lateral_mm']:.2f} / {p['min_vertical_mm']:.2f} | "
            f"{'**FAIL**' if p['status'] == 'fail' else p['status']} | {notes} |"
        )
    lines += ["", "| Plate | Result | Slicer |", "|---|---|---|"]
    lines += [
        f"| {p['plate']} | {'**FAIL**' if p['status'] == 'fail' else 'ok'} | {'; '.join(p['slicer_messages'])} |"
        for p in plates
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n")


def main() -> None:
    report = run()
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=1) + "\n")
    write_markdown(report)
    failed = [p["part"] for p in report["parts"] if p["status"] == "fail"]
    failed += [p["plate"] for p in report["plates"] if p["status"] == "fail"]
    warned = sum(p["status"] == "warn" for p in report["parts"])
    print(
        f"printability: {len(report['parts'])} parts, {len(report['plates'])} plates, {len(failed)} fail, {warned} warn; "
        f"kit {report['kit_filament_g']:.0f} g, {report['kit_print_time_h']:.0f} h"
    )
    if failed:
        print("FAIL: " + ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
