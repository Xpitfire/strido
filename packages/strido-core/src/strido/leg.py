"""Leg kinematics of Strido including the knee four-bar linkages.

Joint convention (identical to the Unitree Go2 so policies/tools transfer):
    hip   q1: rotation about +x (forward); positive moves the foot to +y (left).
    thigh q2: rotation about +y; 0 = femur straight down, positive = knee backwards.
    calf  q3: rotation about +y relative to the femur; negative = knee bent.

Actuation (measured from CAD, see hardware/kinematics.yaml):
    * hip servo drives q1 directly,
    * thigh servo drives q2 directly (coaxial with the femur pivot),
    * the knee *drive* servo turns an arm; a parallelogram (arm, short link,
      crank) copies the arm angle onto a crank coaxial with the femur pivot; a
      second four-bar (crank, long link, tibia crank, femur) turns the tibia.
      The drive servo therefore commands the crank's absolute angle psi in the
      hip-housing frame, and q3 is a non-linear function of (q2, psi).

All functions are pure and work in SI units.
"""

import math
from dataclasses import dataclass

import numpy as np

from .geometry import LEG_NAMES, LEGS, LegGeometry


def _angle(vector: np.ndarray) -> float:
    return math.atan2(vector[1], vector[0])


def _polar(radius: float, angle: float) -> np.ndarray:
    return np.array([radius * math.cos(angle), radius * math.sin(angle)])


def _cross(a: np.ndarray, b: np.ndarray) -> float:
    return float(a[0] * b[1] - a[1] * b[0])


def circle_intersection(
    c0: np.ndarray | tuple[float, float], r0: float, c1: np.ndarray | tuple[float, float], r1: float, side: float
) -> np.ndarray | None:
    """Intersection of two circles; `side` picks the solution with sign(cross(c1-c0, p-c0)) == side."""
    c0 = np.asarray(c0, dtype=float)
    c1 = np.asarray(c1, dtype=float)
    delta = c1 - c0
    distance = float(np.hypot(*delta))
    if distance < 1e-12 or distance > r0 + r1 or distance < abs(r0 - r1):
        return None
    along = (r0 * r0 - r1 * r1 + distance * distance) / (2 * distance)
    height = math.sqrt(max(r0 * r0 - along * along, 0.0))
    base = c0 + along * delta / distance
    normal = np.array([-delta[1], delta[0]]) / distance
    candidate = base + height * normal
    if np.sign(_cross(delta, candidate - c0)) == side or height == 0.0:
        return candidate
    return base - height * normal


def knee_point(leg: LegGeometry, thigh: float) -> np.ndarray:
    return np.array([-leg.thigh_length * math.sin(thigh), -leg.thigh_length * math.cos(thigh)])


def foot_point_plane(leg: LegGeometry, thigh: float, calf: float) -> np.ndarray:
    absolute = thigh + calf
    return knee_point(leg, thigh) + np.array(
        [-leg.calf_length * math.sin(absolute), -leg.calf_length * math.cos(absolute)]
    )


def _calf_direction_angle(thigh: float, calf: float) -> float:
    # Direction (atan2 in the u-v plane) of the knee->foot vector.
    return -math.pi / 2 - (thigh + calf)


@dataclass(frozen=True)
class LinkageBranches:
    forward_side: float  # side for solving the tibia pin from the crank
    inverse_side: float  # side for solving the crank pin from the tibia


def _branches(leg: LegGeometry) -> LinkageBranches:
    knee = knee_point(leg, leg.cad_thigh_angle)
    crank_b = _polar(leg.crank_radius_b, leg.cad_crank_angle + leg.crank_offset)
    tibia_pin = knee + _polar(
        leg.tibia_radius, _calf_direction_angle(leg.cad_thigh_angle, leg.cad_calf_angle) + leg.tibia_offset
    )
    forward = float(np.sign(_cross(crank_b - knee, tibia_pin - knee)))
    inverse = float(np.sign(_cross(tibia_pin, crank_b)))
    return LinkageBranches(forward, inverse)


_BRANCHES = {name: _branches(LEGS[name]) for name in LEG_NAMES}


def calf_from_crank(name: str, thigh: float, crank: float) -> float | None:
    """Forward linkage: knee joint angle q3 for a thigh angle and crank angle psi (None if unreachable)."""
    leg = LEGS[name]
    knee = knee_point(leg, thigh)
    crank_b = _polar(leg.crank_radius_b, crank + leg.crank_offset)
    tibia_pin = circle_intersection(knee, leg.tibia_radius, crank_b, leg.long_link, _BRANCHES[name].forward_side)
    if tibia_pin is None:
        return None
    calf_direction = _angle(tibia_pin - knee) - leg.tibia_offset
    absolute = -math.pi / 2 - calf_direction
    return math.remainder(absolute - thigh, 2 * math.pi)


def crank_from_calf(name: str, thigh: float, calf: float) -> float | None:
    """Inverse linkage: crank angle psi the knee drive servo must hold for (q2, q3)."""
    leg = LEGS[name]
    knee = knee_point(leg, thigh)
    tibia_pin = knee + _polar(leg.tibia_radius, _calf_direction_angle(thigh, calf) + leg.tibia_offset)
    crank_b = circle_intersection(
        np.zeros(2), leg.crank_radius_b, tibia_pin, leg.long_link, _BRANCHES[name].inverse_side
    )
    if crank_b is None:
        return None
    return math.remainder(_angle(crank_b) - leg.crank_offset, 2 * math.pi)


def linkage_points(name: str, thigh: float, calf: float) -> dict[str, np.ndarray] | None:
    """All pivot positions in the leg plane for drawing/collision posing."""
    leg = LEGS[name]
    crank = crank_from_calf(name, thigh, calf)
    if crank is None:
        return None
    drive = np.array([leg.drive_u, leg.drive_v])
    knee = knee_point(leg, thigh)
    return {
        "thigh_pivot": np.zeros(2),
        "knee": knee,
        "foot": foot_point_plane(leg, thigh, calf),
        "drive": drive,
        "arm_pin": drive + _polar(leg.arm_radius, crank),
        "crank_a": _polar(leg.crank_radius_a, crank),
        "crank_b": _polar(leg.crank_radius_b, crank + leg.crank_offset),
        "tibia_pin": knee + _polar(leg.tibia_radius, _calf_direction_angle(thigh, calf) + leg.tibia_offset),
        "crank_angle": np.array([crank]),
    }


def transmission_angles(name: str, thigh: float, calf: float) -> tuple[float, float] | None:
    """Transmission angles (rad) of the knee four-bar at the long link ends; near 0 or pi = singular."""
    points = linkage_points(name, thigh, calf)
    if points is None:
        return None
    link = points["tibia_pin"] - points["crank_b"]
    at_crank = abs(math.remainder(_angle(link) - _angle(points["crank_b"]), math.pi))
    at_tibia = abs(math.remainder(_angle(link) - _angle(points["tibia_pin"] - points["knee"]), math.pi))
    return at_crank, at_tibia


def foot_position(name: str, q: tuple[float, float, float]) -> np.ndarray:
    """Foot centre in the base frame for joint angles (q1, q2, q3)."""
    leg = LEGS[name]
    hip, thigh, calf = q
    plane = foot_point_plane(leg, thigh, calf)
    local = np.array([plane[0], leg.thigh_offset_y, plane[1]])
    cos_h, sin_h = math.cos(hip), math.sin(hip)
    rotated = np.array([local[0], cos_h * local[1] - sin_h * local[2], sin_h * local[1] + cos_h * local[2]])
    return np.array([leg.hip_x, leg.hip_y, leg.hip_z]) + rotated


def inverse_kinematics(name: str, foot: np.ndarray) -> tuple[float, float, float] | None:
    """Joint angles placing the foot centre at `foot` (base frame); knee bent backwards."""
    leg = LEGS[name]
    relative = np.asarray(foot, dtype=float) - np.array([leg.hip_x, leg.hip_y, leg.hip_z])
    offset = leg.thigh_offset_y
    radial_sq = relative[1] ** 2 + relative[2] ** 2 - offset**2
    if radial_sq <= 0:
        return None
    depth = math.sqrt(radial_sq)
    hip = math.atan2(relative[2], relative[1]) - math.atan2(-depth, offset)
    hip = math.remainder(hip, 2 * math.pi)
    u, v = relative[0], -depth
    l1, l2 = leg.thigh_length, leg.calf_length
    cos_calf = (u * u + v * v - l1 * l1 - l2 * l2) / (2 * l1 * l2)
    if abs(cos_calf) > 1:
        return None
    calf = -math.acos(cos_calf)
    direction = math.atan2(-u, -v)
    thigh = direction - math.atan2(l2 * math.sin(calf), l1 + l2 * math.cos(calf))
    return hip, thigh, calf
