"""Velocity-commanded trot gait for Strido (shared by MuJoCo, Gazebo and the robot).

A deliberately simple, deterministic open-loop gait: diagonal leg pairs swing
alternately; stance feet slide backwards at the commanded body velocity and the
swing foot lands Raibert-style half a stride ahead. Output is joint angles in
Go2 order (FL, FR, RL, RR x hip, thigh, calf), clamped to the generated joint
and knee-drive limits.
"""

import math
from dataclasses import dataclass

import numpy as np

from . import leg as leg_kinematics
from .geometry import LEG_NAMES, LEGS

PHASE_OFFSET = {"FL": 0.0, "RR": 0.0, "FR": 0.5, "RL": 0.5}
REST_HEIGHT_M = 0.07  # legs folded, belly just above the ground: start-up and spawn pose


@dataclass
class GaitConfig:
    body_height: float = 0.17  # hip axis above the foot centres [m]
    period: float = 0.40  # full gait cycle [s]
    duty: float = 0.5  # stance fraction
    step_height: float = 0.035  # swing apex [m]
    stance_widening: float = 0.0  # extra lateral foot offset [m]
    max_linear: tuple[float, float] = (0.30, 0.15)  # |vx|, |vy| [m/s]
    max_yaw_rate: float = 1.0  # [rad/s]


class TrotGait:
    def __init__(self, config: GaitConfig | None = None) -> None:
        self.config = config or GaitConfig()
        self.time = 0.0
        self.command = np.zeros(3)  # vx, vy, wz
        self.nominal: dict[str, np.ndarray] = {}
        for name in LEG_NAMES:
            leg = LEGS[name]
            side = math.copysign(1.0, leg.hip_y)
            self.nominal[name] = np.array(
                [
                    leg.hip_x,
                    leg.hip_y + leg.thigh_offset_y + side * self.config.stance_widening,
                    -self.config.body_height,
                ]
            )

    def set_command(self, vx: float, vy: float, wz: float) -> None:
        limit_x, limit_y = self.config.max_linear
        self.command = np.array(
            [
                np.clip(vx, -limit_x, limit_x),
                np.clip(vy, -limit_y, limit_y),
                np.clip(wz, -self.config.max_yaw_rate, self.config.max_yaw_rate),
            ]
        )

    def foot_targets(self) -> dict[str, np.ndarray]:
        cfg = self.config
        stance_time = cfg.period * cfg.duty
        moving = np.linalg.norm(self.command) > 1e-4
        targets = {}
        for name in LEG_NAMES:
            nominal = self.nominal[name]
            velocity = np.array(
                [self.command[0] - self.command[2] * nominal[1], self.command[1] + self.command[2] * nominal[0], 0.0]
            )
            stride = velocity * stance_time
            if not moving:
                targets[name] = nominal.copy()
                continue
            phase = (self.time / cfg.period + PHASE_OFFSET[name]) % 1.0
            if phase < cfg.duty:
                s = phase / cfg.duty
                offset = stride * (0.5 - s)
                lift = 0.0
            else:
                s = (phase - cfg.duty) / (1.0 - cfg.duty)
                offset = stride * (s - 0.5)
                lift = cfg.step_height * math.sin(math.pi * s)
            targets[name] = nominal + offset + np.array([0.0, 0.0, lift])
        return targets

    def step(self, dt: float) -> np.ndarray:
        """Advance the gait clock and return 12 joint targets."""
        self.time += dt
        return joint_targets(self.foot_targets())


def joint_targets(feet: dict[str, np.ndarray]) -> np.ndarray:
    q: list[float] = []
    for name in LEG_NAMES:
        solution = leg_kinematics.inverse_kinematics(name, feet[name])
        assert solution is not None, f"{name}: foot target out of reach {feet[name]}"
        q.extend(clamp_leg(name, solution))
    return np.array(q)


def clamp_leg(name: str, q: tuple[float, float, float] | np.ndarray) -> tuple[float, float, float]:
    """Clamp to the joint limits and the knee-drive crank window (the firmware enforces the same
    limits in actuator space: hip, thigh, crank, then the calf range)."""
    leg = LEGS[name]
    hip = float(np.clip(q[0], leg.hip_min, leg.hip_max))
    thigh = float(np.clip(q[1], leg.thigh_min, leg.thigh_max))
    calf = float(np.clip(q[2], leg.calf_min, leg.calf_max))
    crank = leg_kinematics.crank_from_calf(name, thigh, calf)
    if crank is not None and not (leg.crank_min <= crank <= leg.crank_max):
        crank = float(np.clip(crank, leg.crank_min, leg.crank_max))
        solved = leg_kinematics.calf_from_crank(name, thigh, crank)
        assert solved is not None, f"{name}: crank {crank:.3f} rad inside its window must have a calf solution"
        calf = solved
    return hip, thigh, calf


def stand_pose(height: float = 0.17) -> np.ndarray:
    gait = TrotGait(GaitConfig(body_height=height))
    return joint_targets(gait.foot_targets())
