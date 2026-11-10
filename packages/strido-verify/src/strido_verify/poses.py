"""Named joint poses of the whole robot used by the verification and render tools.

A pose maps each leg (FL, FR, RL, RR) to (hip, thigh, calf) joint angles in radians.
"""

import numpy as np

from strido import leg as leg_kinematics
from strido.gait import GaitConfig, TrotGait
from strido.geometry import LEG_NAMES, LEGS

Pose = dict[str, tuple[float, float, float]]
TROT_COMMAND_VX = 0.3  # m/s, the gait's maximum forward command
TROT_SAMPLES = 8


def stand_pose(name: str, height: float = 0.17) -> tuple[float, float, float]:
    """Joint angles that put the foot of leg `name` straight below its hip at `height` metres."""
    leg = LEGS[name]
    foot = np.array([leg.hip_x, leg.hip_y + leg.thigh_offset_y, -height])
    return tuple(leg_kinematics.inverse_kinematics(name, foot))


def standing(height: float) -> Pose:
    return {name: stand_pose(name, height) for name in LEG_NAMES}


def trot_phases(samples: int = TROT_SAMPLES) -> dict[str, Pose]:
    """Equally spaced phases of one trot cycle at the maximum forward command."""
    config = GaitConfig()
    gait = TrotGait(config)
    gait.set_command(TROT_COMMAND_VX, 0.0, 0.0)
    result = {}
    for index in range(samples):
        gait.time = index * config.period / samples
        q = np.array(gait.step(0.0)).reshape(4, 3)
        result[f"trot_{index}of{samples}"] = {name: tuple(q[i]) for i, name in enumerate(LEG_NAMES)}
    return result


def hips_abducted(outward: bool) -> Pose:
    """Standing at 170 mm with every hip at its outward (or inward) limit."""
    pose = {}
    for name in LEG_NAMES:
        leg = LEGS[name]
        left = leg.hip_y > 0
        hip = (leg.hip_max if left else leg.hip_min) if outward else (leg.hip_min if left else leg.hip_max)
        stand = stand_pose(name, 0.17)
        pose[name] = (hip, stand[1], stand[2])
    return pose


def operating_poses() -> dict[str, Pose]:
    """Every pose the robot is expected to pass through in normal operation."""
    return {
        "stand_170mm": standing(0.17),
        "crouch_120mm": standing(0.12),
        "tall_210mm": standing(0.21),
        **trot_phases(),
        "hips_out": hips_abducted(outward=True),
        "hips_in": hips_abducted(outward=False),
    }
