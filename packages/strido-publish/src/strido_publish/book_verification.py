"""Verification page of the catalogue book, computed from the reports the gates wrote."""

import json
from collections import Counter

import yaml

from strido.workspace import build_dir, path
from strido_verify import electronics

from . import bom

NOT_RUN = ("not run: `make verify`", "warn")


def verification_rows() -> list[tuple[str, str, str]]:
    """(check, result, css class) from the reports the gates wrote; a missing report reads "not run"."""
    rows = []
    interference = build_dir("verify") / "interference.json"
    if interference.is_file():
        poses = json.loads(interference.read_text())
        failures = sum(row["verdict"] == "FAIL" for rows_ in poses.values() for row in rows_)
        rows.append(
            (
                f"Interference (every solid, {len(poses)} poses)",
                f"{failures} unexplained overlaps",
                "ok" if not failures else "fail",
            )
        )
    else:
        rows.append(("Interference", *NOT_RUN))
    fits_path = path("docs/verification/data/fits.json")
    if fits_path.is_file():
        fits = json.loads(fits_path.read_text())
        screws = Counter(screw["status"] for screw in fits["screws"])
        seat_fail = sum(seat["status"] == "fail" for seat in fits["seats"])
        rows.append(
            (
                f"Screw fits ({sum(screws.values())} screws) and {len(fits['seats'])} bearing seats",
                f"{screws['ok']} ok, {screws['warn']} with a finishing action, {screws['fail'] + seat_fail} fail",
                "ok" if not screws["fail"] and not seat_fail else "fail",
            )
        )
    else:
        rows.append(("Screw fits and bearing seats", *NOT_RUN))
    clearance_path = path("docs/verification/data/clearance.json")
    if clearance_path.is_file():
        clearance = json.loads(clearance_path.read_text())
        pairs = Counter(pair["status"] for pair in clearance["pairs"])
        rows.append(
            (
                f"Moving-part clearance ({len(clearance['poses'])} operating poses)",
                f"{pairs['fail']} fail, {pairs['warn']} tight (< 1 mm), {pairs['interface']} rotational interfaces",
                "ok" if not pairs["fail"] else "fail",
            )
        )
    else:
        rows.append(("Moving-part clearance", *NOT_RUN))
    printability = path("docs/verification/data/printability.json")
    if printability.is_file():
        report = json.loads(printability.read_text())
        failed = sum(p["status"] == "fail" for p in report["parts"] + report["plates"])
        rows.append(
            (
                f"Printability ({len(report['parts'])} parts, {len(report['plates'])} plates sliced in PrusaSlicer)",
                f"{failed} fail, {sum(p['status'] == 'warn' for p in report['parts'])} thin-wall warnings; "
                f"{report['kit_filament_g'] / 1000:.1f} kg, {report['kit_print_time_h']:.0f} h",
                "ok" if not failed else "fail",
            )
        )
    else:
        rows.append(("Printability", "not run: `make printability`", "warn"))
    sensors = build_dir("verify") / "sensor_fov.json"
    if sensors.is_file():
        poses = json.loads(sensors.read_text())
        blocked = sum(len(pose["lidar_blocked_deg"]) for pose in poses.values())
        camera = max(pose["camera_self_view_fraction"] for pose in poses.values())
        rows.append(
            (
                f"Sensors ({len(poses)} poses)",
                f"{blocked} LiDAR rays blocked, camera sees {100 * camera:.1f} % robot",
                "ok" if not blocked and camera == 0.0 else "fail",
            )
        )
    else:
        rows.append(("Sensors", *NOT_RUN))
    findings = electronics.run_checks(
        yaml.safe_load(electronics.SOURCE.read_text()),
        electronics.BOARD_CONFIG,
        yaml.safe_load(electronics.WIRING.read_text()),
    )
    failed = [finding for finding in findings if not finding.ok]
    rows.append(
        (
            "Electronics vs firmware (pins, I²C, servo channels, fuses, wires)",
            f"{len(findings) - len(failed)} of {len(findings)} checks pass",
            "ok" if not failed else "fail",
        )
    )
    wiring = path("docs/verification/data/wiring.json")
    if wiring.is_file():
        report = json.loads(wiring.read_text())["findings"]
        statuses = [finding["status"] for finding in report]
        rows.append(
            (
                "Wiring harness (reach, stock, hip loops, ports, clearance in every pose)",
                f"{statuses.count('ok')} of {len(statuses)} checks pass, {statuses.count('warn')} warn",
                "fail" if "fail" in statuses else "warn" if "warn" in statuses else "ok",
            )
        )
    else:
        rows.append(("Wiring harness", "not run: `make verify`", "warn"))
    counts, _ = bom.cad_counts()
    lines = yaml.safe_load(bom.BOM.read_text())["lines"]
    _, problems = bom.coverage([(line, bom.cheapest(line)) for line in lines], counts)
    rows.append(
        (
            "Purchasing: every CAD part and fastener in the BOM",
            "all covered" if not problems else f"{len(problems)} coverage problems",
            "ok" if not problems else "fail",
        )
    )
    return rows
