"""Loads for the strength check: leg geometry from hardware/kinematics.yaml, the knee linkage swept over
the joint limits with the knee servo at stall, and the landing force (hardware/strength.yaml)."""

from collections import defaultdict

import numpy as np
import yaml

from strido import leg as leg_kinematics
from strido.geometry import LEG_NAMES
from strido.workspace import path

CONFIG = yaml.safe_load(path("hardware/strength.yaml").read_text())
KINEMATICS = path("hardware/kinematics.yaml")
JOINT_LIMITS = path("hardware/joint_limits.yaml")
G = 9.81
POSE_STEP_DEG = 2.5


def leg_geometry() -> dict[str, float]:
    """Largest link lengths and lever arms over the four legs (mm), from the measured kinematics."""
    legs = yaml.safe_load(KINEMATICS.read_text())["legs_step_raw"]
    lengths = defaultdict(float)
    pairs = {
        "femur": ("femur_pivot_yz", "knee_yz"),
        "tibia": ("knee_yz", "foot_yz"),
        "arm": ("drive_servo_yz", "arm_pin_yz"),
        "crank_a": ("femur_pivot_yz", "crank_pin_a_yz"),
        "crank_b": ("femur_pivot_yz", "crank_pin_b_yz"),
        "knee_crank": ("knee_yz", "tibia_pin_yz"),
        "short_link": ("arm_pin_yz", "crank_pin_a_yz"),  # pin-to-pin: the buckling length
        "long_link": ("crank_pin_b_yz", "tibia_pin_yz"),
    }
    for leg in legs.values():
        for name, (a, b) in pairs.items():
            lengths[name] = max(lengths[name], float(np.linalg.norm(np.subtract(leg[a], leg[b]))))
        lengths["hip_lever"] = max(lengths["hip_lever"], abs(leg["leg_plane_x_mm"] - leg["hip_axis_point_step_mm"][0]))
    return dict(lengths)


def sine_between(a: np.ndarray, b: np.ndarray) -> float:
    """|sin| of the angle between two plane vectors (the lever arm fraction of a force along b on lever a)."""
    return abs(float(a[0] * b[1] - a[1] * b[0])) / float(np.linalg.norm(a) * np.linalg.norm(b))


def linkage_extremes() -> dict[str, float]:
    """Largest knee-linkage forces (N) and knee torque (N·m) with the knee servo at stall, over every
    thigh/calf pose inside hardware/joint_limits.yaml whose crank angle is inside its limit too (all
    four legs, POSE_STEP_DEG grid). The crank limit keeps the drive parallelogram away from its dead
    points, where sin α → 0."""
    stall = CONFIG["loads"]["servo_stall_torque_nm"]
    limits = yaml.safe_load(JOINT_LIMITS.read_text())["limits"]
    worst = defaultdict(float)
    for name in LEG_NAMES:
        thighs = np.radians(np.arange(*limits[name]["thigh_deg"], POSE_STEP_DEG))
        calves = np.radians(np.arange(*limits[name]["calf_deg"], POSE_STEP_DEG))
        crank_low, crank_high = np.radians(limits[name]["crank_deg"])
        for thigh in thighs:
            for calf in calves:
                p = leg_kinematics.linkage_points(name, thigh, calf)
                if p is None or not crank_low <= p["crank_angle"][0] <= crank_high:
                    continue
                # the leg model works in metres: T [N·m] / lever [m] = F [N]
                arm, short = p["arm_pin"] - p["drive"], p["crank_a"] - p["arm_pin"]
                crank_b, long = p["crank_b"], p["tibia_pin"] - p["crank_b"]
                knee_lever = p["tibia_pin"] - p["knee"]
                f_short = stall / (np.linalg.norm(arm) * sine_between(arm, short))
                crank_torque = f_short * np.linalg.norm(p["crank_a"]) * sine_between(p["crank_a"], short)
                f_long = crank_torque / (np.linalg.norm(crank_b) * sine_between(crank_b, long))
                knee_torque = f_long * np.linalg.norm(knee_lever) * sine_between(knee_lever, long)
                for key, value in (("short_link_n", f_short), ("long_link_n", f_long), ("knee_nm", knee_torque)):
                    worst[key] = max(worst[key], float(value))
    return dict(worst)


def joint_loads(geometry: dict[str, float]) -> dict[str, float]:
    """Worst-case torques (N·m) and forces (N): servo stall torques (knee linkage swept over the joint
    range) and the landing force along the leg for pins and bearings."""
    loads = CONFIG["loads"]
    stall = loads["servo_stall_torque_nm"]
    foot = loads["impact_factor"] * loads["robot_mass_kg"] * G / 2
    linkage = linkage_extremes()
    return {
        "foot_n": foot,
        "thigh_nm": stall,
        "hip_nm": stall,
        **linkage,
        "knee_landing_nm": foot * geometry["tibia"] / 1000,
        "knee_joint_n": foot + linkage["long_link_n"],
    }
