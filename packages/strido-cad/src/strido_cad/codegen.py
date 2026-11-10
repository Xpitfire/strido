"""Generate language bindings of the measured robot geometry.

Sources of truth: `hardware/kinematics.yaml` (measured from CAD by
`strido_cad.extract_kinematics`) and `hardware/joint_limits.yaml` (collision /
linkage sweep by `strido_verify.rom`). This module writes:

* packages/strido-core/src/strido/geometry.py      (Python, used by sim/ROS/tools)
* firmware/strido_esp32s3/lib/strido_core/include/strido/geometry_generated.h  (C++, ESP32)

`--check` fails if a generated file differs from what would be written, so CI
catches hand edits or a stale regeneration.

Leg-plane convention (all legs identical): origin at the thigh (femur) pivot,
u forward (+x of the robot), v up (+z). Angles are atan2(v, u) in radians.
"""

import argparse
import math
import sys

import yaml

from .paths import JOINT_LIMITS, KINEMATICS, REPO

SOURCE = KINEMATICS
LIMITS = JOINT_LIMITS
# Assembly reference: with every servo at its 1500 us neutral the femur is mounted
# 45 deg back from vertical and the knee crank at 35 deg (docs/assembly). One value
# for all legs keeps the build simple; the ROM limits are clipped to +-85 deg of it.
NEUTRAL_DEG = {"hip": 0.0, "thigh": 45.0, "crank": 35.0}
PY_OUT = REPO / "packages/strido-core/src/strido/geometry.py"
CPP_OUT = REPO / "firmware/strido_esp32s3/lib/strido_core/include/strido/geometry_generated.h"
LEG_ORDER = ("FL", "FR", "RL", "RR")  # Go2 /joint_states order


def leg_plane(raw):
    pivot_y, pivot_z = raw["femur_pivot_yz"]

    def uv(point):
        return (-(point[0] - pivot_y), point[1] - pivot_z)

    return {
        name: uv(raw[f"{name}_yz"])
        for name in (
            "femur_pivot",
            "knee",
            "drive_servo",
            "arm_pin",
            "crank_pin_a",
            "crank_pin_b",
            "tibia_link_end",
            "tibia_pin",
            "foot",
        )
    }


def angle(vector):
    return math.atan2(vector[1], vector[0])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def norm(vector):
    return math.hypot(vector[0], vector[1])


def leg_constants(raw):
    p = leg_plane(raw)
    knee, foot, tibia_pin = p["knee"], p["foot"], p["tibia_pin"]
    crank_a, crank_b, drive, arm = p["crank_pin_a"], p["crank_pin_b"], p["drive_servo"], p["arm_pin"]
    thigh_vector = knee
    calf_vector = sub(foot, knee)
    # Joint angle from straight down, positive = foot moves backwards (Go2 sign).
    thigh_angle = -math.pi / 2 - angle(thigh_vector)
    calf_absolute = -math.pi / 2 - angle(calf_vector)
    return {
        "thigh_length": norm(thigh_vector) / 1000.0,
        "calf_length": norm(calf_vector) / 1000.0,
        "foot_radius": raw["foot_radius_mm"] / 1000.0,
        "drive_u": drive[0] / 1000.0,
        "drive_v": drive[1] / 1000.0,
        "arm_radius": norm(sub(arm, drive)) / 1000.0,
        "short_link": norm(sub(crank_a, arm)) / 1000.0,
        "crank_radius_a": norm(crank_a) / 1000.0,
        "crank_radius_b": norm(crank_b) / 1000.0,
        "crank_offset": math.remainder(angle(crank_b) - angle(crank_a), 2 * math.pi),
        "long_link": norm(sub(p["tibia_link_end"], crank_b)) / 1000.0,
        "tibia_radius": norm(sub(tibia_pin, knee)) / 1000.0,
        "tibia_offset": math.remainder(angle(sub(tibia_pin, knee)) - angle(calf_vector), 2 * math.pi),
        "cad_thigh_angle": thigh_angle,
        "cad_calf_angle": math.remainder(calf_absolute - thigh_angle, 2 * math.pi),
        "cad_crank_angle": angle(crank_a),
    }


def _direction(out_axis, joint_axis) -> float:
    """+1 when a positive servo rotation (right-hand about the horn axis) is a positive joint rotation."""
    return 1.0 if sum(a * b for a, b in zip(out_axis, joint_axis)) > 0 else -1.0


def build_model():
    document = yaml.safe_load(SOURCE.read_text())
    limits_document = yaml.safe_load(LIMITS.read_text())
    limits = limits_document["limits"]
    servo_half_travel_deg = limits_document["servo_half_travel_deg"]  # single source: strido_verify.rom
    legs = {}
    joint_axes_step = {"hip": (0.0, -1.0, 0.0), "thigh": (1.0, 0.0, 0.0), "knee_drive": (-1.0, 0.0, 0.0)}
    for name in LEG_ORDER:
        constants = leg_constants(document["legs_step_raw"][name])
        out = document["legs_step_raw"][name]["servo_output_axis_step"]
        constants["dir_hip"] = _direction(out["hip"], joint_axes_step["hip"])
        constants["dir_thigh"] = _direction(out["thigh"], joint_axes_step["thigh"])
        constants["dir_crank"] = _direction(out["knee_drive"], joint_axes_step["knee_drive"])
        leg_limits = limits[name]
        for joint, key in (("hip", "hip_deg"), ("thigh", "thigh_deg"), ("calf", "calf_deg"), ("crank", "crank_deg")):
            low, high = leg_limits[key]
            if joint in NEUTRAL_DEG:
                low = max(low, NEUTRAL_DEG[joint] - servo_half_travel_deg)
                high = min(high, NEUTRAL_DEG[joint] + servo_half_travel_deg)
            constants[f"{joint}_min"] = math.radians(low)
            constants[f"{joint}_max"] = math.radians(high)
        for joint, value in NEUTRAL_DEG.items():
            constants[f"neutral_{joint}"] = math.radians(value)
        base = document["legs_base"][name]
        constants["hip_x"] = base["hip_mm"][0] / 1000.0
        constants["hip_y"] = base["hip_mm"][1] / 1000.0
        constants["hip_z"] = base["hip_mm"][2] / 1000.0
        constants["thigh_offset_y"] = base["leg_plane_offset_mm"] / 1000.0
        legs[name] = constants
    return legs


FIELDS = (
    "hip_x",
    "hip_y",
    "hip_z",
    "thigh_offset_y",
    "thigh_length",
    "calf_length",
    "foot_radius",
    "drive_u",
    "drive_v",
    "arm_radius",
    "short_link",
    "crank_radius_a",
    "crank_radius_b",
    "crank_offset",
    "long_link",
    "tibia_radius",
    "tibia_offset",
    "cad_thigh_angle",
    "cad_calf_angle",
    "cad_crank_angle",
    "hip_min",
    "hip_max",
    "thigh_min",
    "thigh_max",
    "calf_min",
    "calf_max",
    "crank_min",
    "crank_max",
    "neutral_hip",
    "neutral_thigh",
    "neutral_crank",
    "dir_hip",
    "dir_thigh",
    "dir_crank",
)
HEADER = "GENERATED by strido_cad.codegen from hardware/kinematics.yaml - do not edit."


def render_python(legs):
    lines = [
        f'"""{HEADER}',
        "",
        "SI units (metres, radians). Leg-plane: u forward, v up, origin at thigh pivot.",
        '"""',
        "",
    ]
    lines.append("from dataclasses import dataclass")
    lines.append("")
    lines.append("")
    lines.append("@dataclass(frozen=True)")
    lines.append("class LegGeometry:")
    for field in FIELDS:
        lines.append(f"    {field}: float")
    lines.append("")
    lines.append("")
    lines.append(f"LEG_NAMES = {LEG_ORDER!r}")
    lines.append("LEGS = {")
    for name in LEG_ORDER:
        values = ", ".join(f"{field}={legs[name][field]!r}" for field in FIELDS)
        lines.append(f"    {name!r}: LegGeometry({values}),")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _cpp_float(value: float) -> str:
    text = f"{value:.9g}"
    if "." not in text and "e" not in text:
        text += ".0"
    return text + "f"


def render_cpp(legs):
    lines = [
        f"// {HEADER}",
        "// SI units (metres, radians). Leg-plane: u forward, v up, origin at thigh pivot.",
        "#pragma once",
        "",
    ]
    lines.append("namespace strido {")
    lines.append("")
    lines.append("struct LegGeometry {")
    for field in FIELDS:
        lines.append(f"  float {field};")
    lines.append("};")
    lines.append("")
    lines.append("// Order: FL, FR, RL, RR (Go2 /joint_states order).")
    lines.append(f"constexpr LegGeometry kLegs[{len(LEG_ORDER)}] = {{")
    for name in LEG_ORDER:
        values = ", ".join(_cpp_float(legs[name][field]) for field in FIELDS)
        lines.append(f"    {{{values}}},  // {name}")
    lines.append("};")
    lines.append("")
    lines.append("}  // namespace strido")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated files are stale")
    args = parser.parse_args()
    legs = build_model()
    outputs = {PY_OUT: render_python(legs), CPP_OUT: render_cpp(legs)}
    stale = []
    for path, content in outputs.items():
        if args.check:
            if not path.is_file() or path.read_text() != content:
                stale.append(path)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            print(f"wrote {path.relative_to(REPO)}")
    if stale:
        print("stale generated files:", *[str(p.relative_to(REPO)) for p in stale], sep="\n  ")
        sys.exit(1)


if __name__ == "__main__":
    main()
