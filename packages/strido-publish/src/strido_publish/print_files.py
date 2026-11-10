"""Export every printed part in its print orientation, check printability, build plates.

* hardware/print/stl/<part>.stl  - Strido new and modified parts (committed)
* hardware/print/print_list.md   - every printed part (upstream + Strido): file, quantity,
                                   size on the bed, overhang share, settings
* hardware/print/plates/*.3mf    - parts packed onto 220 x 220 mm plates (send to the slicer)

Checks (exit 1 on failure): closed manifold mesh, part fits a 220 x 220 x 250 mm bed
(Ender-3 class; upstream minimum is 150 x 150), resting on z=0.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import trimesh

from strido.workspace import path, repo_root
from strido_cad import assembly, catalog
from strido_cad.geom import lay_flat, to_manifold

from .print_bridges import bridge_hole_steps

REPO = repo_root()
STL_OUT = path("hardware/print/stl")
PLATES = path("hardware/print/plates")
PRINT_LIST = path("hardware/print/print_list.md")
PRINT_JSON = path("build/print/print_parts.json")
BED_MM = (220.0, 220.0, 250.0)
PLATE_MM = 220.0  # same as the stated minimum bed (BED_MM)
# Gap between parts on a plate: at 4 mm the supports of neighbouring parts produce conflicting tool
# paths (PrusaSlicer 2.9 logs "gcode path conflicts"); 10 mm slices cleanly (strido_verify.printability).
PLATE_GAP_MM = 10.0
PLATE_EDGE_MM = 5.0  # free margin to the bed edge
OVERHANG_DEG = 45.0
SECONDARY_COLOUR = {
    "top_shell_sensor",
    "front_shell_display",
    "back_shell_button",
    "bottom_shell",
    "left_shoulder",
    "right_shoulder",
}
# Upstream parts printed on another face than the published STL (which is often its CAD pose: tall on a
# small footprint): resting face in the kit STL frame. Chosen per part for bed contact and least overhang,
# never with a link's long axis upright (layers across its load); strido_verify.printability slices each.
REORIENT = {
    "inner_tibia": (1, 0, 0),  # flat side down, 14.4 mm tall instead of 135 mm upright (1638 mm² on the bed)
    "outer_tibia": (-1, 0, 0),  # its flat side is the other face: the two halves are mirror images
    "short_link": (-1, 0, 0),  # flat: no supports needed at all
    "hip_bearing_pin": (0, -1, 0),  # on its flat side: no supports needed
    "femur": (1, 0, 0),  # on its side: 1930 mm² on the bed instead of 2 mm², overhang 14 % -> 4 %
    "femur_servo_connector": (1, 0, 0),  # flat disc instead of on its 6 mm edge
    "servo_mount_top_bracket": (0, -1, 0),  # flat, 5.8 mm tall instead of 56 mm on a 19 x 6 mm footprint
    "side_body_beam": (1, 0, 0),  # flat, 6.5 mm tall instead of 25 mm on its edge; overhang 6 % -> 1 %
    "right_shoulder": (0, 0, 1),  # upside down like the left shoulder's file: overhang 13 % -> 5 %
    # Servo mounts lie like a U (a builder's advice): overhang 13 % -> 2 %, 19 mm tall instead of 56 mm, and
    # 10 of their 13 M3 pilots (servo ears, bracket) print vertical; the hip-horn and hip-pivot pilots lie
    # horizontal (ADR-009: harden with thin CA if one does not grip).
    "left_servo_mount": (-1, 0, 0),
    "left_servo_mount_fl": (-1, 0, 0),
    "right_servo_mount": (-1, 0, 0),
    "right_servo_mount_fr": (-1, 0, 0),
}


def overhang_share(mesh: trimesh.Trimesh) -> float:
    """Area share of downward faces steeper than 45 deg that are not on the bed."""
    normals = mesh.face_normals
    centres = mesh.triangles_center
    down = normals[:, 2] < -np.cos(np.radians(OVERHANG_DEG))
    off_bed = centres[:, 2] > 0.3
    return float(mesh.area_faces[down & off_bed].sum() / mesh.area)


FACE_NAMES = {(1, 0, 0): "+X", (-1, 0, 0): "-X", (0, 1, 0): "+Y", (0, -1, 0): "-Y", (0, 0, 1): "+Z", (0, 0, -1): "-Z"}


def best_orientation(mesh: trimesh.Trimesh) -> tuple[str, float]:
    """Axis-aligned resting face (in the file's frame) with the least unsupported overhang."""
    best = ("-Z", overhang_share(mesh))
    for down, label in FACE_NAMES.items():
        trial = mesh.copy()
        trial.apply_transform(lay_flat(trial, down))
        share = overhang_share(trial)
        if share < best[1] - 1e-6:
            best = (label, share)
    return best


def upstream_print_mesh(stl: Path) -> trimesh.Trimesh:
    mesh = trimesh.load(stl, force="mesh")
    mesh.apply_translation(
        (-mesh.bounds[0][0] - mesh.extents[0] / 2, -mesh.bounds[0][1] - mesh.extents[1] / 2, -mesh.bounds[0][2])
    )
    return mesh


def main():
    manifest = catalog.build_parts()
    instances = catalog.full_assembly()
    counts = Counter(item.part for item in instances if item.kind == "printed")
    rows = []
    failures = []
    STL_OUT.mkdir(parents=True, exist_ok=True)
    new_parts = {entry["part"]: entry for entry in manifest["parts"]}
    upstream_files = {}
    for item in instances:
        if item.kind == "printed" and item.part not in new_parts:
            upstream_files.setdefault(item.part, item)
    for part, count in sorted(counts.items()):
        name = part.split("/")[1]
        if part in new_parts:
            entry = new_parts[part]
            mesh = trimesh.load(entry["mesh"], force="mesh")
            if entry["print_down"] is None:  # modified upstream part: keep the upstream STL orientation
                source = next(
                    i for i in assembly.upstream_instances() if i.part == entry["replaces"] and _same_place(i, entry)
                )
                mesh.apply_transform(np.linalg.inv(source.matrix))
                mesh.apply_translation((-mesh.bounds.mean(axis=0)[0], -mesh.bounds.mean(axis=0)[1], -mesh.bounds[0][2]))
            else:
                mesh.apply_transform(lay_flat(mesh, entry["print_down"]))
            path = STL_OUT / f"{name}.stl"
            mesh.export(path)
            origin = (
                "Strido (new)"
                if entry["replaces"] is None
                else f"Strido (modified upstream {entry['replaces'].split('/')[1]})"
            )
            note = entry["note"]
            declared_supports = bool(entry["supports"])  # e.g. a pocket ceiling the overhang share misses
        else:
            item = upstream_files[part]
            note = ""
            declared_supports = False
            if item.meta.get("source") == "upstream STL":  # copied into the kit, published orientation kept
                mesh = upstream_print_mesh(item.mesh)
                path = STL_OUT / f"{name}.stl"
                mesh.export(path)
                origin = "upstream STL"
            elif item.meta.get("source") == "strido derived":  # upstream STL modified in its own frame
                mesh = upstream_print_mesh(item.mesh)
                path = STL_OUT / f"{name}.stl"
                mesh.export(path)
                origin = f"Strido (modified upstream {item.meta['derived_from'].split('/')[1]})"
                note = item.meta["derived_note"]
            else:  # STEP-only upstream part (foot spacer, hip pin): exported from the STEP
                mesh = trimesh.load(item.mesh, force="mesh")
                mesh.apply_transform(lay_flat(mesh, (0, 0, -1)))
                path = STL_OUT / f"{name}.stl"
                mesh.export(path)
                origin = "upstream STEP (no upstream STL published)"
        if name in REORIENT:
            mesh.apply_transform(lay_flat(mesh, REORIENT[name]))
            mesh.export(path)
            note = (note + "; " if note else "") + "re-oriented from the published STL: more bed contact, less overhang"
        mesh, bridged = bridge_hole_steps(mesh)
        if bridged:
            mesh.export(path)
            cut = f"{len(bridged)} hole step{'s' if len(bridged) > 1 else ''} cut for bridging (hole overhang trick)"
            if not all(step.from_bed for step in bridged):  # a seat above the bed: the slicer supports its bore
                cut += "; block supports in the bearing bore so the step bridges"
            note = (note + "; " if note else "") + cut
        best_down, best_share = best_orientation(mesh)
        if origin == "upstream STL" and name not in REORIENT and best_share + 0.02 < overhang_share(mesh):
            published = (
                f"published orientation; resting it on its {best_down} face lowers overhang to {100 * best_share:.0f} %"
            )
            note = published + ("; " + note if note else "")
        manifold_ok = to_manifold(mesh).status().name == "NoError"
        extents = mesh.extents
        fits = bool(extents[0] <= BED_MM[0] and extents[1] <= BED_MM[1] and extents[2] <= BED_MM[2]) or bool(
            extents[1] <= BED_MM[0] and extents[0] <= BED_MM[1] and extents[2] <= BED_MM[2]
        )
        on_bed = abs(mesh.bounds[0][2]) < 1e-3
        share = overhang_share(mesh)
        if not (manifold_ok and fits and on_bed):
            failures.append((name, manifold_ok, fits, on_bed))
        rows.append(
            {
                "part": name,
                "qty": count,
                "file": str(Path(path).relative_to(REPO)),
                "origin": origin,
                "bed_mm": [round(float(v), 1) for v in extents],
                "overhang_share": round(share, 3),
                "supports": share > 0.02 or declared_supports,
                "colour": "secondary (lime)" if name in SECONDARY_COLOUR else "primary (graphite)",
                "volume_cm3": round(abs(mesh.volume) / 1000.0, 1),
                "note": note,
                "mesh": mesh,
            }
        )
    write_list(rows)
    PRINT_JSON.parent.mkdir(parents=True, exist_ok=True)
    PRINT_JSON.write_text(json.dumps([{k: v for k, v in row.items() if k != "mesh"} for row in rows], indent=1))
    build_plates(rows)
    print(f"{len(rows)} printed part types, {sum(r['qty'] for r in rows)} pieces")
    if failures:
        print(f"PRINTABILITY FAIL: {failures}")
        sys.exit(1)


def _same_place(upstream_item, entry) -> bool:
    if "lower_shoulder_frame" not in entry["part"]:
        return True
    front = entry["part"].endswith("_front")
    centre_y = trimesh.load(upstream_item.mesh).bounds.mean(axis=0)
    world = upstream_item.matrix @ np.append(centre_y, 1.0)
    return (world[1] < 0) == front


def write_list(rows):
    total = sum(r["volume_cm3"] * r["qty"] for r in rows)
    lines = [
        "# Print list",
        "",
        "Generated by `strido_publish.print_files`. Every part (upstream Yertle and Strido) prints from "
        "`hardware/print/stl/`, oriented for printing; `hardware/print/plates/` holds ready 3MF plates.",
        "",
        "Servo mounts and `servo_mount_top_bracket`: print with X-Y hole compensation -0.15 mm so their M3 "
        "pilots grip (ADR-009); otherwise harden those pilots with a drop of thin CA glue before driving the screws "
        "(anaerobic thread locker is not for plastic: it does not cure there and can crack PETG). The compensation "
        "acts on vertical holes: the servo mounts lie like a U, so their hip-horn and hip-pivot pilots are horizontal "
        "and get the CA treatment if a screw spins.",
        "",
        "Hole steps (a bearing seat narrowing to a smaller hole above it) are cut for bridging in the STLs: the "
        "two layers above the step print a slot, then a square (see the notes). Where the note says so, block "
        "supports in the bearing bore in the slicer: the seat sits above the bed and would otherwise be supported.",
        "",
        "Settings (all parts unless noted): PETG or PLA+, 0.2 mm layers, 3 walls (1.2 mm), 5 top/bottom layers, "
        "30 % gyroid infill, snug supports where listed, brim on parts taller than 40 mm. PrusaSlicer profile: "
        "`hardware/print/prusaslicer.ini` (File > Import > Import Config). Checked: closed manifold, fits a "
        "220 x 220 x 250 mm bed, and every part and plate slices without stability warnings with exactly these "
        "settings (`make printability`, docs/verification/printability.md).",
        "",
        "| Part | Qty | Colour | File (in `hardware/print/`) | Size on bed (mm) | Supports | Source | Note |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        size = " x ".join(f"{v:.0f}" for v in row["bed_mm"])
        supports = f"yes ({100 * row['overhang_share']:.0f} % overhang)" if row["supports"] else "no"
        lines.append(
            f"| {row['part']} | {row['qty']} | {row['colour']} | `{Path(row['file']).relative_to('hardware/print')}` | {size} | {supports} | {row['origin']} | {row['note']} |"
        )
    lines += [
        "",
        f"Total solid volume of all pieces: {total:.0f} cm³ (filament ≈ {total * 1.27 * 0.55:.0f} g PETG at the settings above; "
        "budget 1.2 kg incl. brims, supports and test prints).",
        "",
    ]
    PRINT_LIST.parent.mkdir(parents=True, exist_ok=True)
    PRINT_LIST.write_text("\n".join(lines))


def build_plates(rows):
    """Greedy shelf packing of every piece onto 220 x 220 mm plates, one 3MF per plate and colour."""
    PLATES.mkdir(parents=True, exist_ok=True)
    for old in PLATES.glob("*.3mf"):
        old.unlink()
    for colour in ("primary (graphite)", "secondary (lime)"):
        pieces = []
        for row in rows:
            if row["colour"] != colour:
                continue
            for k in range(row["qty"]):
                pieces.append((row["part"], k, row["mesh"]))
        pieces.sort(key=lambda p: -p[2].extents[1])
        edge = PLATE_EDGE_MM
        plates = []  # per plate: {"items": [...], "x", "y", "shelf"} (open shelf cursor)
        for name, k, mesh in pieces:
            w, d = mesh.extents[0], mesh.extents[1]
            assert w <= PLATE_MM - 2 * edge and d <= PLATE_MM - 2 * edge, f"{name} does not fit a plate"
            target = None
            for plate in plates:  # first fit: the open shelf, else a new shelf below it
                if plate["x"] + w <= PLATE_MM - edge and plate["y"] + d <= PLATE_MM - edge:
                    target = plate
                    break
                below = plate["y"] + plate["shelf"]
                if below + d <= PLATE_MM - edge:
                    plate.update(x=edge, y=below, shelf=0.0)
                    target = plate
                    break
            if target is None:
                target = {"items": [], "x": edge, "y": edge, "shelf": 0.0}
                plates.append(target)
            placed = mesh.copy()
            placed.apply_translation((target["x"] - placed.bounds[0][0], target["y"] - placed.bounds[0][1], 0.0))
            target["items"].append((f"part_{name}_{k + 1}", placed))  # trimesh drops 3MF nodes named "camera*"
            target["x"] += w + PLATE_GAP_MM
            target["shelf"] = max(target["shelf"], d + PLATE_GAP_MM)
        plates = [plate["items"] for plate in plates]
        tag = "graphite" if colour.startswith("primary") else "lime"
        for index, plate in enumerate(plates, start=1):
            scene = trimesh.Scene()
            for name, mesh in plate:
                scene.add_geometry(mesh, node_name=name)
            scene.export(PLATES / f"plate_{tag}_{index:02d}.3mf")


if __name__ == "__main__":
    main()
