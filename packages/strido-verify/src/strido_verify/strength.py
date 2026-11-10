"""Strength of the printed legs and their joints under the loads the robot can produce on itself.

Loads (hardware/strength.yaml; leg geometry from hardware/kinematics.yaml and the strido leg model):

* Foot force of a hard landing: F_foot = k · m · g / 2 (k = impact factor, one diagonal pair).
* Joint torques: each servo's stall torque (the largest torque it applies; back-driving it from
  outside takes more, a documented limit). T_thigh = T_hip = T_stall.
* Knee linkage, swept over every pose inside the joint limits with the knee servo at stall:
  F_short = T_stall / (r_arm · sin α), F_long = T_crank / (r_crank_b · sin β), T_knee = F_long · r_knee · sin γ
  (α, β, γ: angles between each lever and its link). Pins and bearings also carry the landing force.

Checks (safety factor S = allowable / actual; fail below 1.5, warn below 2.0; a failing check
accepted by an ADR in strength.yaml reports as a warning):

* Link bending in the leg plane at the weakest section, walls only (infill ignored): sigma = M / W,
  against the PETG strength along the layers, or across them (layer adhesion) when the link's long
  axis points up in its print orientation.
* Link tension/compression sigma = F / A_min and Euler buckling F_cr = pi^2 · E · I / (K · L)^2 in and
  across the leg plane (I: sections in series along the link, L: pin spacing).
* Screw shear tau = F / A_s against 0.577 · Rp0.2, and hole bearing pressure p = F / (d · t) in the
  printed part (t = material the screw passes, from the fit report).
* Bearings: radial load against the static rating C0.
* Thread-forming screws: pull-out force F = tau_layer · pi · d · L_e and the tightening torque that
  reaches it, T = k · F · d; the recommended torque is half of that.

Inputs also include the fit report (docs/verification/data/fits.json) and the fastener placements
of `make verify` (build/verify/fasteners_upstream.json). Writes docs/verification/strength.md and
docs/verification/data/strength.json; exit 1 on any failure.
"""

import json
import math
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass

import numpy as np

from strido.workspace import path

from .strength_loads import CONFIG, joint_loads, leg_geometry
from .strength_report import render
from .strength_sections import Section, weakest_section
from .strength_threads import thread_torques

FITS_JSON = path("docs/verification/data/fits.json")
PLACEMENTS = path("build/verify/fasteners_upstream.json")
REPORT_JSON = path("docs/verification/data/strength.json")
REPORT_MD = path("docs/verification/strength.md")
# Printed part that plays each link role (the Strido stiff long link replaces the upstream one, ADR-010).
LINK_PARTS = {"short_link": "short_link", "long_link": "stiff_long_link"}


@dataclass
class Check:
    id: str
    parts: list[str]
    what: str
    formula: str
    actual: float
    allowable: float
    unit: str
    safety: float
    status: str
    note: str = ""


def grade(safety: float, check_id: str) -> tuple[str, str]:
    """Status and note. A failing check listed under `accepted` in strength.yaml is a warning with its
    ADR, but only down to the safety factor the ADR accepted (`min_safety`): a worse result fails again."""
    limits = CONFIG["safety"]
    status = "fail" if safety < limits["fail_below"] else "warn" if safety < limits["warn_below"] else "ok"
    accepted = CONFIG.get("accepted", {}).get(check_id)
    if status == "fail" and accepted and safety >= accepted["min_safety"]:
        return "warn", f"accepted deviation ({accepted['adr']}, S ≥ {accepted['min_safety']}): {accepted['action']}"
    return status, ""


def check(
    id_: str, parts: list[str], what: str, formula: str, actual: float, allowable: float, unit: str, note: str = ""
) -> Check:
    safety = allowable / actual
    status, accepted_note = grade(safety, id_)
    return Check(
        id_,
        parts,
        what,
        formula,
        round(actual, 2),
        round(allowable, 1),
        unit,
        round(safety, 2),
        status,
        accepted_note or note,
    )


def screw_holes(fits: dict, joint: str) -> list[dict]:
    """Every printed part a screw of `joint` passes, with hole diameter, span and engaged length."""
    return [part for screw in fits["screws"] if screw["joint"] == joint for part in screw["parts"]]


def bolt_circle(joint: str) -> tuple[int, float]:
    """Screws per joint and their smallest distance (mm) to the pattern centre, from the CAD placements."""
    groups = defaultdict(list)
    for placement in json.loads(PLACEMENTS.read_text())["placements"]:
        if placement["joint"] == joint:
            groups[placement["body"]].append(placement["head"])
    count = min(len(heads) for heads in groups.values())
    radius = min(
        float(np.linalg.norm(np.subtract(heads, np.mean(heads, axis=0)), axis=1).min()) for heads in groups.values()
    )
    return count, radius


def allowable_mpa(section: Section) -> float:
    material = CONFIG["material"]
    return material["layer_adhesion_mpa"] if section.across_layers else material["tensile_xy_mpa"]


def link_checks(
    loads: dict[str, float], geometry: dict[str, float], sections: dict[str, Section], fits: dict
) -> list[Check]:
    modulus_mpa = CONFIG["material"]["modulus_gpa"] * 1000
    femur, tibia = sections["femur"], [sections["inner_tibia"], sections["outer_tibia"]]
    checks = [
        check(
            "femur_bending",
            ["femur"],
            "femur bending at its weakest section (thigh servo stall torque)",
            "σ = T_thigh / W",
            loads["thigh_nm"] * 1000 / femur.w_bend_mm3,
            allowable_mpa(femur),
            "MPa",
        ),
        check(
            "tibia_bending",
            ["inner_tibia", "outer_tibia"],
            "tibia halves bending (knee torque, shared by the two halves)",
            "σ = T_knee / (W_inner + W_outer)",
            loads["knee_nm"] * 1000 / sum(s.w_bend_mm3 for s in tibia),
            min(allowable_mpa(s) for s in tibia),
            "MPa",
        ),
    ]
    k_out = CONFIG["loads"]["buckling_out_of_plane_k"]
    for link, force in (("short_link", loads["short_link_n"]), ("long_link", loads["long_link_n"])):
        section, part = sections[link], LINK_PARTS[link]
        length = geometry[link]
        # The pins push along their line; a shaft beside it (offset e) also bends: secant formula for an
        # eccentric pinned column, the bending amplified as the force approaches the in-plane buckling load.
        half_angle = length / 2 * math.sqrt(force / (modulus_mpa * section.i_in_mm4))
        amplification = 1 / math.cos(half_angle) if half_angle < math.pi / 2 else math.inf
        stress = force / section.area_mm2 + force * section.pin_offset_mm * amplification / section.w_bend_mm3
        checks.append(
            check(
                f"{link}_axial",
                [part],
                f"{link.replace('_', ' ')} tension/compression (pin-line offset e = {section.pin_offset_mm:.1f} mm)",
                "σ = F / A + F · e · sec(L/2 · √(F / E I)) / W",
                stress,
                allowable_mpa(section),
                "MPa",
            )
        )
        in_plane_n = math.pi**2 * modulus_mpa * section.i_in_mm4 / length**2
        out_of_plane_n = math.pi**2 * modulus_mpa * section.i_out_mm4 / (k_out * length) ** 2
        checks.append(
            check(
                f"{link}_buckling",
                [part],
                f"{link.replace('_', ' ')} buckling (pinned in the leg plane, K = {k_out} across it)",
                "F_cr = π² · E · I / (K · L)²",
                force,
                min(in_plane_n, out_of_plane_n),
                "N",
            )
        )
        eyes = [
            hole
            for joint in ("arm_pin", "crank_pins", "tibia_link_pin")
            for hole in screw_holes(fits, joint)
            if hole["part"] == part
        ]
        pressure = max(force / (hole["hole_d_mm"] * hole["span_mm"]) for hole in eyes)
        checks.append(
            check(
                f"{link}_eye",
                [part],
                f"{link.replace('_', ' ')} pin hole bearing pressure",
                "p = F / (d · t)",
                pressure,
                CONFIG["material"]["tensile_xy_mpa"],
                "MPa",
            )
        )
    return checks


def joint_checks(loads: dict[str, float], fits: dict) -> list[Check]:
    screws = CONFIG["screws"]
    shear_allowable = CONFIG["material"]["shear_factor"] * screws["rp02_mpa"]
    area_m3 = screws["stress_area_mm2"]["M3"]
    checks = []
    for joint, torque_nm, what in (
        ("femur_to_horn", loads["thigh_nm"], "femur on the thigh horn"),
        ("hip_horn", loads["hip_nm"], "hip horn on the servo mount"),
    ):
        count, radius = bolt_circle(joint)
        force = torque_nm * 1000 / (count * radius)
        holes = [hole for hole in screw_holes(fits, joint) if hole["fit"] in ("clearance", "thread-forming")]
        parts = sorted({hole["part"] for hole in holes})
        checks.append(
            check(
                f"{joint}_screws",
                parts,
                f"{count} × M3 shear, {what} (r = {radius:.1f} mm)",
                "τ = T / (n · r · A_s)",
                force / area_m3,
                shear_allowable,
                "MPa",
            )
        )
        pressure = max(force / (hole["hole_d_mm"] * hole["span_mm"]) for hole in holes)
        checks.append(
            check(
                f"{joint}_holes",
                parts,
                f"printed hole bearing pressure, {what}",
                "p = T / (n · r · d · t)",
                pressure,
                CONFIG["material"]["tensile_xy_mpa"],
                "MPa",
            )
        )
    for joint, force, shear_planes, what in (
        ("arm_pin", loads["short_link_n"], 1, "arm pin (short link)"),
        ("tibia_link_pin", loads["long_link_n"], 2, "tibia link pin (long link)"),
        ("knee_axle", loads["knee_joint_n"] / 2, 1, "knee axle screw (one per side)"),
    ):
        parts = sorted({hole["part"] for hole in screw_holes(fits, joint)})
        checks.append(
            check(
                f"{joint}_shear",
                parts,
                f"M3 shear, {what}",
                f"τ = F / ({shear_planes} · A_s)",
                force / (shear_planes * area_m3),
                shear_allowable,
                "MPa",
            )
        )
    femur_bores = [hole for hole in screw_holes(fits, "knee_axle") if hole["part"] == "femur"]
    pressure = max(loads["knee_joint_n"] / 2 / (hole["hole_d_mm"] * hole["engaged_mm"]) for hole in femur_bores)
    checks.append(
        check(
            "knee_axle_bore",
            ["femur"],
            "knee axle bearing pressure in the femur pilot",
            "p = F / (d · L_e)",
            pressure,
            CONFIG["material"]["tensile_xy_mpa"],
            "MPa",
        )
    )
    bearings = CONFIG["bearings"]
    for line, size, force, what in (
        ("bearing_633zz", "633ZZ", loads["knee_joint_n"] / 2, "knee, two per leg"),
        ("bearing_6805", "6805-2RS", loads["short_link_n"] + loads["long_link_n"], "shoulder crank"),
        ("bearing_625zz", "625ZZ", loads["foot_n"], "hip pivot"),
    ):
        checks.append(
            check(
                f"{line}_static",
                [line],
                f"{size} static radial load ({what})",
                "S = C0 / F_r",
                force,
                bearings[size]["c0_n"],
                "N",
                bearings[size]["source"],
            )
        )
    return checks


def write_reports(
    loads: dict, geometry: dict, sections: dict[str, Section], checks: list[Check], torques: list[dict]
) -> None:
    document = {
        "loads": {k: round(v, 2) for k, v in loads.items()},
        "geometry_mm": {k: round(v, 1) for k, v in geometry.items()},
        "sections": {
            k: {f: round(v, 1) if isinstance(v, float) else v for f, v in asdict(s).items()}
            for k, s in sections.items()
        },
        "checks": [asdict(c) for c in checks],
        "thread_torques": torques,
        "config": CONFIG,
    }
    REPORT_JSON.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n")
    REPORT_MD.write_text(render(CONFIG, loads, geometry, checks, torques))


def main() -> int:
    wall = CONFIG["print"]["wall_mm"]
    sections = {
        role: weakest_section(LINK_PARTS.get(role, role), wall)
        for role in ("femur", "inner_tibia", "outer_tibia", "short_link", "long_link")
    }
    geometry = leg_geometry()
    loads = joint_loads(geometry)
    fits = json.loads(FITS_JSON.read_text())
    checks = link_checks(loads, geometry, sections, fits) + joint_checks(loads, fits)
    torques = thread_torques(fits, CONFIG)
    write_reports(loads, geometry, sections, checks, torques)
    for c in checks:
        print(f"{c.status:4s} S={c.safety:6.2f}  {c.what}")
    return 1 if any(c.status == "fail" for c in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
