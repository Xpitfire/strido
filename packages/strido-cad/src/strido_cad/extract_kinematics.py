"""Measure leg kinematics and the knee linkage from the upstream STEP assembly.

Every number in `hardware/kinematics.yaml` comes from cylinder axes of the CAD
solids (servo output splines, bearing bores, link pins) - nothing is typed in by
hand. The output defines:

* the robot base frame (REP-103: x forward, y left, z up) relative to the STEP
  frame,
* per-leg hip (abduction), thigh and knee axes, link lengths and foot centre,
* the two four-bar linkages that drive the knee from the lower leg servo.

Run:  make kinematics
"""

import math

import numpy as np
import yaml

from .features import cylinders
from .paths import KINEMATICS, UPSTREAM_STEP
from .step_tree import read_step_leaves

STEP_PATH = UPSTREAM_STEP
OUTPUT = KINEMATICS

# STEP assembly prefix of each leg and its Go2-style name. Front is -Y in the
# STEP frame, right is -X (see docs/design.md).
LEGS = {
    "FR": "Yertle Single v2/legs:1/fr leg_assem",
    "RR": "Yertle Single v2/legs:1/br leg_assem",
    "FL": "Yertle Single v2/legs(Mirror):1/fr leg_assem",
    "RL": "Yertle Single v2/legs(Mirror):1/br leg_assem",
}
AXIS_TOLERANCE_MM = 0.3


def leaves_under(leaves, prefix):
    return [leaf for leaf in leaves if leaf.path_str.startswith(prefix)]


def find(leaves, *needles, depth=None, prefix_depth=None):
    found = []
    for leaf in leaves:
        name = leaf.path_str.lower()
        if all(needle.lower() in name for needle in needles):
            if depth is not None and len(leaf.path) - prefix_depth != depth:
                continue
            found.append(leaf)
    return found


def axes_of(leaf, radius_min, radius_max, holes=None):
    result = []
    for cylinder in cylinders(leaf.shape):
        if radius_min <= cylinder.radius_mm <= radius_max and (holes is None or cylinder.is_hole == holes):
            if cylinder.angle_deg < 300:
                continue
            result.append(cylinder)
    return result


def unique_axes(cylinder_list):
    unique = []
    for cylinder in cylinder_list:
        if not any(
            other.contains_line(cylinder.axis_point_mm, cylinder.axis_direction, AXIS_TOLERANCE_MM) for other in unique
        ):
            unique.append(cylinder)
    return unique


def plane_point(cylinder, axis_index):
    """2D (y, z) STEP coordinates of an axis parallel to STEP X."""
    assert abs(abs(cylinder.axis_direction[axis_index]) - 1.0) < 1e-3, cylinder.axis_direction
    point = cylinder.axis_point_mm
    return np.array([point[1], point[2]])


def measure_leg(leaves, prefix):
    leg = leaves_under(leaves, prefix)
    assert leg, prefix
    prefix_depth = len(leg[0].path) - (len(leg[0].path) - len(prefix.split("/")))
    del prefix_depth
    base_depth = len(prefix.split("/"))

    hip_servo = [leaf for leaf in leg if "servo_blue" in leaf.path[-1] and len(leaf.path) == base_depth + 1]
    assert len(hip_servo) == 1, [leaf.path_str for leaf in hip_servo]
    hip_axis = axes_of(hip_servo[0], 8.4, 8.6, holes=False)
    assert len(hip_axis) == 1
    hip = hip_axis[0]
    assert abs(abs(hip.axis_direction[1]) - 1) < 1e-3, "hip axis must run along STEP Y"

    leg_servos = [leaf for leaf in leg if "servo_blue" in leaf.path[-1] and len(leaf.path) > base_depth + 1]
    assert len(leg_servos) == 2
    servo_axes = [axes_of(servo, 8.4, 8.6, holes=False)[0] for servo in leg_servos]

    femur = [leaf for leaf in leg if "femur" in leaf.path[-1].lower()]
    assert len(femur) == 1
    femur_cyl = cylinders(femur[0].shape)
    pivot_candidates = [c for c in femur_cyl if 12.0 < c.radius_mm < 14.5]
    assert pivot_candidates
    femur_pivot = plane_point(pivot_candidates[0], 0)
    knee_candidates = [c for c in femur_cyl if 1.3 < c.radius_mm < 1.6 and c.is_hole]
    knee = max(knee_candidates, key=lambda c: np.linalg.norm(plane_point(c, 0) - femur_pivot))
    knee_point = plane_point(knee, 0)

    thigh_servo = min(servo_axes, key=lambda c: np.linalg.norm(plane_point(c, 0) - femur_pivot))
    drive_servo = max(servo_axes, key=lambda c: np.linalg.norm(plane_point(c, 0) - femur_pivot))
    assert np.linalg.norm(plane_point(thigh_servo, 0) - femur_pivot) < AXIS_TOLERANCE_MM, "thigh servo not coaxial"
    drive_point = plane_point(drive_servo, 0)

    short_link = [leaf for leaf in leg if "28mm link rod" in leaf.path[-1]]
    short_holes = unique_axes(axes_of(short_link[0], 1.4, 1.6, holes=True))
    assert len(short_holes) == 2
    short_points = [plane_point(c, 0) for c in short_holes]
    # Arm-horn end is the hole closer to the drive servo.
    short_points.sort(key=lambda p: np.linalg.norm(p - drive_point))
    arm_pin, crank_pin_a = short_points

    long_bushings = [leaf for leaf in leg if leaf.path[-1].startswith("bushing") and "link rod v22" in leaf.path_str]
    long_points = [plane_point(axes_of(b, 1.4, 1.6, holes=True)[0], 0) for b in long_bushings]
    assert len(long_points) == 2
    long_points.sort(key=lambda p: np.linalg.norm(p - femur_pivot))
    crank_pin_b, tibia_link_end = long_points

    tibia_leaves = [leaf for leaf in leg if "tibia" in leaf.path_str.lower() and "bearing" not in leaf.path[-1]]
    tibia_cyl = [c for leaf in tibia_leaves for c in cylinders(leaf.shape)]
    tibia_pin = [c for c in tibia_cyl if 1.45 < c.radius_mm < 1.55 and not c.is_hole]
    assert tibia_pin, "tibia link pin not found"
    tibia_pin_point = plane_point(tibia_pin[0], 0)
    foot_candidates = [c for c in tibia_cyl if 11.5 < c.radius_mm < 12.5 and c.angle_deg >= 300]
    assert foot_candidates
    foot_point = plane_point(foot_candidates[0], 0)
    foot_radius = foot_candidates[0].radius_mm
    foot_x_span = foot_candidates[0].span_mm

    def out_axis(servo_leaf, boss):
        """Unit vector from the servo body centre towards its output spline (horn side).

        Uses the spline centre-screw hole (r ~1.25 mm), which sits at the horn end.
        """
        spline = [
            c
            for c in cylinders(servo_leaf.shape)
            if 1.2 < c.radius_mm < 1.3
            and c.is_hole
            and c.contains_line(boss.axis_point_mm, boss.axis_direction, AXIS_TOLERANCE_MM)
        ]
        assert len(spline) == 1, servo_leaf.path_str
        centre = spline[0].axis_point_mm + spline[0].axis_direction * np.mean(spline[0].span_mm)
        direction = boss.axis_direction * np.sign(np.dot(centre - servo_leaf.centroid_mm, boss.axis_direction))
        return direction.round(6).tolist()

    thigh_leaf = next(leaf for leaf, axis in zip(leg_servos, servo_axes) if axis is thigh_servo)
    drive_leaf = next(leaf for leaf, axis in zip(leg_servos, servo_axes) if axis is drive_servo)
    return {
        "servo_output_axis_step": {
            "hip": out_axis(hip_servo[0], hip),
            "thigh": out_axis(thigh_leaf, thigh_servo),
            "knee_drive": out_axis(drive_leaf, drive_servo),
        },
        "hip_axis_point_step_mm": hip.axis_point_mm.tolist(),
        "femur_pivot_yz": femur_pivot.tolist(),
        "knee_yz": knee_point.tolist(),
        "drive_servo_yz": drive_point.tolist(),
        "arm_pin_yz": arm_pin.tolist(),
        "crank_pin_a_yz": crank_pin_a.tolist(),
        "crank_pin_b_yz": crank_pin_b.tolist(),
        "tibia_link_end_yz": tibia_link_end.tolist(),
        "tibia_pin_yz": tibia_pin_point.tolist(),
        "foot_yz": foot_point.tolist(),
        "foot_radius_mm": foot_radius,
        "foot_x_span_mm": list(foot_x_span),
        "leg_plane_x_mm": float(np.mean(foot_x_span)),
    }


def angle(vector):
    return math.atan2(vector[1], vector[0])


def summarise(raw):
    """Lengths and angles in the leg plane; STEP (y, z) with +y backwards."""
    pivot = np.array(raw["femur_pivot_yz"])
    knee = np.array(raw["knee_yz"])
    drive = np.array(raw["drive_servo_yz"])
    arm = np.array(raw["arm_pin_yz"])
    crank_a = np.array(raw["crank_pin_a_yz"])
    crank_b = np.array(raw["crank_pin_b_yz"])
    link_end = np.array(raw["tibia_link_end_yz"])
    tibia_pin = np.array(raw["tibia_pin_yz"])
    foot = np.array(raw["foot_yz"])
    return {
        "thigh_length_mm": float(np.linalg.norm(knee - pivot)),
        "calf_length_mm": float(np.linalg.norm(foot - knee)),
        "drive_to_pivot_mm": float(np.linalg.norm(pivot - drive)),
        "arm_radius_mm": float(np.linalg.norm(arm - drive)),
        "short_link_mm": float(np.linalg.norm(crank_a - arm)),
        "crank_radius_a_mm": float(np.linalg.norm(crank_a - pivot)),
        "crank_radius_b_mm": float(np.linalg.norm(crank_b - pivot)),
        "crank_ab_angle_deg": float(math.degrees(angle(crank_b - pivot) - angle(crank_a - pivot))),
        "long_link_mm": float(np.linalg.norm(link_end - crank_b)),
        "long_link_to_tibia_pin_mm": float(np.linalg.norm(tibia_pin - crank_b)),
        "tibia_crank_radius_mm": float(np.linalg.norm(tibia_pin - knee)),
        "tibia_pin_mismatch_mm": float(np.linalg.norm(tibia_pin - link_end)),
        "tibia_crank_to_foot_angle_deg": float(math.degrees(angle(tibia_pin - knee) - angle(foot - knee))),
    }


def main():
    leaves = read_step_leaves(STEP_PATH)
    legs = {name: measure_leg(leaves, prefix) for name, prefix in LEGS.items()}
    summary = {name: summarise(raw) for name, raw in legs.items()}

    hips = {name: np.array(raw["hip_axis_point_step_mm"]) for name, raw in legs.items()}
    pivots = {name: np.array(raw["femur_pivot_yz"]) for name, raw in legs.items()}
    # Base origin: centre of the four hip/thigh axis intersections.
    intersections = {name: np.array([hips[name][0], pivots[name][0], pivots[name][1]]) for name in legs}
    origin_step = np.mean(list(intersections.values()), axis=0)
    # STEP -> base: x_base = -(y_step - y0), y_base = x_step - x0, z_base = z_step - z0.
    rotation = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])

    def to_base(point_step):
        return rotation @ (np.asarray(point_step) - origin_step)

    base_legs = {}
    for name, raw in legs.items():
        hip_point = to_base(intersections[name])
        knee = to_base([raw["leg_plane_x_mm"], *raw["knee_yz"]])
        foot = to_base([raw["leg_plane_x_mm"], *raw["foot_yz"]])
        base_legs[name] = {
            "hip_mm": hip_point.round(3).tolist(),
            "leg_plane_offset_mm": float(raw["leg_plane_x_mm"] - intersections[name][0]),
            "knee_in_step_pose_mm": knee.round(3).tolist(),
            "foot_in_step_pose_mm": foot.round(3).tolist(),
        }

    document = {
        "description": "Measured from upstream/yertle/design/CAD/Yertle_Single_v2.step by strido_cad.extract_kinematics",
        "units": "mm, degrees",
        "base_frame": {
            "convention": "REP-103: x forward, y left, z up; origin = centre of the four hip axis intersections",
            "origin_in_step_mm": origin_step.round(4).tolist(),
            "rotation_step_to_base": rotation.tolist(),
        },
        "legs_step_raw": legs,
        "legs_linkage": summary,
        "legs_base": base_legs,
    }
    OUTPUT.write_text(yaml.safe_dump(document, sort_keys=False, width=160))
    for name in LEGS:
        print(name, {k: round(v, 2) for k, v in summary[name].items()})
        print("   ", base_legs[name])


if __name__ == "__main__":
    main()
