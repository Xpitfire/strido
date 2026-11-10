"""Strido catalogue and assembly book (A4 PDF) and the machine-readable parts catalogue.

    make catalog        # needs `make print`, `make bom`, `make manual` outputs (renders, icons, print list)

Outputs
  docs/catalog/parts.json            every catalogue part: kind, quantity, size, print/buy data, steps
  docs/catalog/strido-catalog.pdf   IKEA-style book: printed parts, purchased parts, hardware bags at 1:1,
                                     shopping plan, tools, every assembly step, wiring, software, verification

Everything comes from the verified CAD assembly and the tracked hardware data; the book adds
layout only. Fasteners are drawn in true millimetres: print at 100 % and lay a screw on the page.
"""

import importlib.metadata
import json
import math
import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import jinja2
import yaml

from strido.workspace import build_dir, path, repo_root
from strido_cad import assembly, catalog
from strido_cad.fastener_meshes import CATALOGUE

from . import bom, book_verification, manual, manual_select, manual_steps, part_titles, pricing

OUT = path("docs/catalog")
PDF = OUT / "strido-catalog.pdf"
PARTS_JSON = OUT / "parts.json"
PRINT_JSON = path("build/print/print_parts.json")
TEMPLATES = Path(__file__).resolve().parent / "templates"
ICON_DIR = path("docs/assembly/img/parts")
STEP_IMAGES = path("docs/assembly/img")
PLATES = path("hardware/print/plates")
SHELLS = {"top_shell_sensor", "front_shell_display", "back_shell_button", "bottom_shell"}
HOMEBREW_LIB = "/opt/homebrew/lib"  # Pango/GObject for WeasyPrint on macOS (brew install pango)
TOOLS = [
    ("Hex keys 1.5 / 2.0 / 2.5 mm", "M2 / M2.5 / M3 socket heads"),
    ("Nut drivers 4.0 / 5.0 / 5.5 mm", "M2 / M2.5 / M3 nuts"),
    ("Drills 2.2 / 2.7 / 3.2 mm (hand or pin vice)", "chase the holes listed in the fits report"),
    ("Flush cutters, deburring tool", "support and brim removal"),
    ("Soldering iron, solder, heat-shrink", "power harness, XT60, OE pull-up"),
    ("Dupont crimp tool + housings", "signal harness"),
    ("Multimeter", "6.0 V UBEC check, 5 V rail, OE voltage"),
    ("Medium thread locker", "screws into metal horns"),
    ("Thin CA glue (liquid)", "hardening weak printed pilots"),
    ("LiPo charger (balance) + LiPo bag", "battery care"),
    ("USB-C cable", "flashing the XIAO ESP32-S3"),
]


# --------------------------------------------------------------------------- data


def load_print_rows() -> dict[str, dict[str, Any]]:
    if not PRINT_JSON.is_file():
        raise FileNotFoundError(f"{PRINT_JSON} is missing: run `make print` first")
    return {row["part"]: row for row in json.loads(PRINT_JSON.read_text())}


def offers_by_cad_part(lines: list[dict[str, Any]], vendors: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Cheapest offer of the BOM line that supplies each CAD part id."""
    result = {}
    for line in lines:
        offer = bom.cheapest(line)
        for cad_id in line.get("cad", {}):
            result[cad_id] = {
                "line": line["id"],
                "line_name": line["name"],
                "vendor": vendors[offer["vendor"]]["name"],
                "sku": offer.get("sku", ""),
                "price_eur": offer["price"],
                "pack": offer.get("pack", 1),
            }
    return result


def part_entries(instances, groups, print_rows, offers) -> list[dict[str, Any]]:
    steps_of: dict[str, set[int]] = defaultdict(set)
    for index, group in enumerate(groups, start=1):
        for instance in group:
            steps_of[manual_select.kind(instance)].add(index)
    parts = [i for i in instances if i.kind not in ("reference", "cable")]  # cables: the wiring cut list
    counts = Counter(manual_select.kind(i) for i in parts)
    kinds = {manual_select.kind(i): i.kind for i in parts}
    sample = {manual_select.kind(i): i for i in parts}
    entries = []
    order = {"printed": 0, "purchased": 1, "fastener": 2}
    for name in sorted(counts, key=lambda n: (order[kinds[n]], n)):
        kind = kinds[name]
        entry: dict[str, Any] = {
            "id": name,
            "kind": kind,
            "title": part_titles.title(name).replace(" (printed)", ""),
            "qty": counts[name],
            "steps": sorted(steps_of[name]),
        }
        icon = ICON_DIR / f"{name}.png"
        if icon.is_file():
            entry["image"] = f"/parts/{name}.png"
        if kind == "printed":
            row = print_rows[name]
            entry.update(
                {
                    "bbox_mm": row["bed_mm"],
                    "file": row["file"],
                    "colour": row["colour"],
                    "supports": row["supports"],
                    "volume_cm3": row["volume_cm3"],
                    "source": row["origin"],
                    "note": row["note"],
                }
            )
        else:
            mesh = assembly.load_mesh(sample[name].mesh)
            entry["bbox_mm"] = [round(float(v), 1) for v in sorted(mesh.extents, reverse=True)]
            if name in offers:
                entry.update({key: offers[name][key] for key in ("vendor", "sku", "price_eur", "pack")})
                entry["bom_line"] = offers[name]["line"]
        entries.append(entry)
    return entries


# --------------------------------------------------------------------------- 1:1 fastener drawings


def fastener_svg(spec: str) -> str:
    """Side view (screws, stand-offs) or top view (nuts, washers) in true millimetres."""
    item = CATALOGUE["items"][spec]
    thread = CATALOGUE["thread"][item["thread"]]
    d, pad = float(thread["d"]), 1.0
    stroke = 'stroke="#1d2428" stroke-width="0.25" fill="#d9dcdf"'
    if item["kind"] == "screw":
        length, head_d, head_h = float(item["length"]), float(thread["dk"]), float(thread["k"])
        if item["standard"] == "iso7380":
            head_d, head_h = head_d * 1.0, head_h * 0.55
        width, height = head_d + 2 * pad, head_h + length + 2 * pad
        x0 = pad + (head_d - d) / 2
        pitch = {2.0: 0.4, 2.5: 0.45, 3.0: 0.5, 5.0: 0.8}.get(d, 0.5)
        threads = "".join(
            f'<line x1="{x0:.2f}" y1="{pad + head_h + y:.2f}" x2="{x0 + d:.2f}" y2="{pad + head_h + y + pitch / 2:.2f}" '
            'stroke="#1d2428" stroke-width="0.12"/>'
            for y in [pitch * i for i in range(1, int(length / pitch))]
        )
        head = (
            f'<rect x="{pad}" y="{pad}" width="{head_d}" height="{head_h}" rx="0.4" {stroke}/>'
            if item["standard"] != "iso7380"
            else f'<path d="M{pad},{pad + head_h} Q{pad + head_d / 2},{pad - head_h * 0.9} {pad + head_d},{pad + head_h} Z" {stroke}/>'
        )
        body = f'<rect x="{x0:.2f}" y="{pad + head_h}" width="{d}" height="{length}" {stroke}/>' + threads
    elif item["kind"] == "standoff":
        length, flats = float(item["length"]), float(item["across_flats"])
        width, height = flats + 2 * pad, length + 2 * pad
        head = f'<rect x="{pad}" y="{pad}" width="{flats}" height="{length}" {stroke.replace("#d9dcdf", "#e3c56b")}/>'
        body = (
            f'<line x1="{pad + flats / 3:.2f}" y1="{pad}" x2="{pad + flats / 3:.2f}" y2="{pad + length}" stroke="#1d2428" stroke-width="0.12"/>'
            f'<line x1="{pad + 2 * flats / 3:.2f}" y1="{pad}" x2="{pad + 2 * flats / 3:.2f}" y2="{pad + length}" stroke="#1d2428" stroke-width="0.12"/>'
        )
    elif item["kind"] == "nut":
        flats = float(thread["s"])
        corner = flats / math.cos(math.pi / 6)
        width = height = corner + 2 * pad
        cx = cy = width / 2
        points = " ".join(
            f"{cx + corner / 2 * math.cos(math.radians(60 * k)):.2f},{cy + corner / 2 * math.sin(math.radians(60 * k)):.2f}"
            for k in range(6)
        )
        head = f'<polygon points="{points}" {stroke}/>'
        body = (
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{d / 2:.2f}" fill="#ffffff" stroke="#1d2428" stroke-width="0.25"/>'
        )
        if item["standard"] == "din985":
            body += f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{d / 2 + 0.6:.2f}" fill="none" stroke="#3d74c9" stroke-width="0.35"/>'
    else:  # washer
        outer = float(thread["washer_od"])
        width = height = outer + 2 * pad
        cx = cy = width / 2
        head = f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{outer / 2:.2f}" {stroke}/>'
        body = f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{d / 2 + 0.1:.2f}" fill="#ffffff" stroke="#1d2428" stroke-width="0.25"/>'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.2f}mm" height="{height:.2f}mm" '
        f'viewBox="0 0 {width:.2f} {height:.2f}">{head}{body}</svg>'
    )


def hardware_bags(entries) -> list[dict[str, Any]]:
    bags = []
    for entry in entries:
        if entry["kind"] != "fastener":
            continue
        item = CATALOGUE["items"][entry["id"]]
        bags.append(
            {
                **entry,
                "svg": fastener_svg(entry["id"]),
                "buy": bom.spare_target(entry["qty"], True),
                "standard": CATALOGUE["standards"][item["standard"]]["title"],
            }
        )
    return bags


def ruler_svg(length_mm: int = 100) -> str:
    """A millimetre ruler drawn in true millimetres: if it measures 100 mm on paper, so do the fasteners."""
    margin = 4  # mm left and right of the scale, room for the 0 and 100 labels
    ticks = []
    for mm in range(length_mm + 1):
        height = 6.0 if mm % 10 == 0 else 4.0 if mm % 5 == 0 else 2.5
        ticks.append(
            f'<line x1="{mm + margin}" y1="0" x2="{mm + margin}" y2="{height}" stroke="#1d2428" stroke-width="0.15"/>'
        )
        if mm % 10 == 0:
            ticks.append(
                f'<text x="{mm + margin}" y="9.5" font-size="2.6" text-anchor="middle" fill="#1d2428">{mm}</text>'
            )
    width = length_mm + 2 * margin
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="11mm" viewBox="0 0 {width} 11">'
        f'<line x1="{margin}" y1="0" x2="{length_mm + margin}" y2="0" stroke="#1d2428" stroke-width="0.3"/>{"".join(ticks)}</svg>'
    )


# --------------------------------------------------------------------------- shopping


def shopping_plan(data: dict[str, Any]) -> dict[str, Any]:
    vendors, lines = data["vendors"], data["lines"]
    result = bom.solve(lines, vendors, lambda vendor: True)
    by_vendor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line, offer in result["chosen"]:
        by_vendor[offer["vendor"]].append(
            {
                "name": line["name"],
                "qty": line["qty"],
                "sku": offer.get("sku", ""),
                "pieces": pricing.pieces_bought(line, offer),
                "cost": pricing.offer_cost(line, offer),
                "status": offer.get("status", ""),
            }
        )
    shops = []
    for vendor_id, rows in sorted(by_vendor.items(), key=lambda item: -sum(r["cost"] for r in item[1])):
        shops.append(
            {
                "name": vendors[vendor_id]["name"],
                "url": vendors[vendor_id].get("url", ""),
                "rows": rows,
                "subtotal": result["subtotal"].get(vendor_id, 0.0),
                "shipping": result["shipping"].get(vendor_id, 0.0),
                "note": vendors[vendor_id].get("note", ""),
            }
        )
    return {"shops": shops, "total": result["total"]}


# --------------------------------------------------------------------------- book


def assembly_steps(groups) -> list[dict[str, Any]]:
    steps = []
    for index, (step, new) in enumerate(zip(manual_steps.STEPS, groups, strict=True), start=1):
        box = [
            {
                "name": name,
                "qty": count,
                "label": label,
                "icon": (ICON_DIR / f"{name}.png").as_uri() if (ICON_DIR / f"{name}.png").is_file() else None,
            }
            for name, count, label in manual.parts_box(new, step.per_leg)
        ]
        steps.append(
            {
                "index": index,
                "title": step.title,
                "per_leg": step.per_leg,
                "box": box,
                "image": (STEP_IMAGES / f"step_{index:02d}.png").as_uri(),
                "instructions": [manual.markdown_inline(text) for text in step.instructions],
            }
        )
    return steps


def render_book(context: dict[str, Any]) -> None:
    """HTML from the template, PDF by WeasyPrint in a child process: on macOS the Pango libraries are found
    through DYLD_FALLBACK_LIBRARY_PATH, which must be set before the interpreter starts (SIP strips it from shells)."""
    environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATES), autoescape=jinja2.select_autoescape(["html"])
    )
    page = build_dir("catalog") / "book.html"
    page.write_text(environment.get_template("book.html.j2").render(**context))
    child_env = dict(os.environ)
    if sys.platform == "darwin":
        child_env.setdefault("DYLD_FALLBACK_LIBRARY_PATH", HOMEBREW_LIB)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "weasyprint",
            "--base-url",
            str(repo_root()),
            "--stylesheet",
            str(TEMPLATES / "book.css"),
            str(page),
            str(PDF),
        ],
        check=True,
        env=child_env,
    )


def main() -> None:
    instances = catalog.full_assembly()
    groups = manual_steps.assign(instances)
    data = yaml.safe_load(bom.BOM.read_text())
    offers = offers_by_cad_part(data["lines"], data["vendors"])
    entries = part_entries(instances, groups, load_print_rows(), offers)
    OUT.mkdir(parents=True, exist_ok=True)
    PARTS_JSON.write_text(
        json.dumps({"generated_by": "strido_publish.book", "parts": entries}, indent=1, ensure_ascii=False) + "\n"
    )
    electronics = yaml.safe_load(path("hardware/electronics.yaml").read_text())
    cut_list = json.loads(path("docs/verification/data/wiring.json").read_text())["cut_list"]  # make verify
    images = [
        path(f"docs/images/{name}.png")
        for name in ("hero_front", "hero_rear", "exploded", "section_side", "xray_top", "wiring")
    ]
    images += [STEP_IMAGES / f"step_{index:02d}.png" for index in range(1, len(groups) + 1)]
    missing = [str(image.relative_to(repo_root())) for image in images if not image.is_file()]
    if missing:
        raise FileNotFoundError(f"run `make manual renders` first; missing: {', '.join(missing)}")
    printed = [e for e in entries if e["kind"] == "printed"]
    purchased = [e for e in entries if e["kind"] == "purchased"]
    non_cad = [line for line in data["lines"] if not line.get("cad")]
    context = {
        "version": importlib.metadata.version("strido-publish"),  # stable across rebuilds (no date churn in the PDF)
        "root": repo_root().as_uri(),
        "printed": printed,
        "purchased": purchased,
        "bags": hardware_bags(entries),
        "non_cad": non_cad,
        "plates": sorted(p.name for p in PLATES.glob("*.3mf")),
        "totals": {
            "printed": sum(e["qty"] for e in printed),
            "purchased": sum(e["qty"] for e in purchased),
            "fasteners": sum(e["qty"] for e in entries if e["kind"] == "fastener"),
            "printed_types": len(printed),
        },
        "shopping": shopping_plan(data),
        "tools": TOOLS,
        "steps": assembly_steps(groups),
        "ruler": ruler_svg(),
        "electronics": electronics,
        "cut_list": cut_list,
        "verification": book_verification.verification_rows(),
        "images": {image.stem: image.as_uri() for image in images if image.parent == path("docs/images")},
    }
    render_book(context)
    print(f"wrote {PARTS_JSON.relative_to(repo_root())} ({len(entries)} part types) and {PDF.relative_to(repo_root())}")


if __name__ == "__main__":
    main()
