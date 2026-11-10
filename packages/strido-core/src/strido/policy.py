"""Numpy runtime for policies exported by strido_sim.rl.train (no torch on the robot).

Observation layout (23): gyro (3), gravity in base frame (3), command vx/vy/wz (3),
previous action (12), gait clock sin/cos (2). Output: 12 actions in [-1, 1]; joint
targets = stand pose + ACTION_SCALE * action (then clamped like the firmware).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

Array = npt.NDArray[np.float64]

ACTION_SCALE = 0.3
GAIT_PERIOD_S = 0.4
OBSERVATION_SIZE = 23
CONTROL_DT = 0.02  # 50 Hz policy
MAX_JOINT_SPEED_RAD_S = 6.0  # firmware slew limit (safety.h max_joint_speed_rad_s)
# Command ranges seen in training: vx, vy [m/s], wz [rad/s]. Commands outside are clipped.
COMMAND_RANGES = ((-0.15, 0.30), (-0.10, 0.10), (-0.6, 0.6))


def clip_command(command: Sequence[float]) -> np.ndarray:
    return np.array([np.clip(value, low, high) for value, (low, high) in zip(command, COMMAND_RANGES)])


def slew_limit(target: np.ndarray, previous: np.ndarray) -> np.ndarray:
    """Same per-step joint speed limit the firmware applies (6 rad/s at 50 Hz = 0.12 rad)."""
    step = MAX_JOINT_SPEED_RAD_S * CONTROL_DT
    return previous + np.clip(target - previous, -step, step)


@dataclass
class MlpPolicy:
    hidden: list[tuple[Array, Array]]
    out: tuple[Array, Array]
    obs_mean: np.ndarray
    obs_var: np.ndarray
    obs_clip: float

    @classmethod
    def load(cls, path: str | Path) -> "MlpPolicy":
        data = np.load(path)
        hidden = []
        index = 0
        while f"w{index}" in data:
            hidden.append((data[f"w{index}"], data[f"b{index}"]))
            index += 1
        assert hidden, f"{path}: no hidden layers"
        assert data["obs_mean"].shape == (OBSERVATION_SIZE,), "policy was trained with a different observation layout"
        return cls(hidden, (data["w_out"], data["b_out"]), data["obs_mean"], data["obs_var"], float(data["obs_clip"]))

    def __call__(self, observation: Sequence[float] | np.ndarray) -> np.ndarray:
        x = np.clip(
            (np.asarray(observation, dtype=np.float32) - self.obs_mean) / np.sqrt(self.obs_var + 1e-8),
            -self.obs_clip,
            self.obs_clip,
        )
        for weight, bias in self.hidden:
            x = np.tanh(weight @ x + bias)
        weight, bias = self.out
        return np.clip(weight @ x + bias, -1.0, 1.0)
