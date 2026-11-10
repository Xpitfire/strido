"""Gymnasium velocity-tracking environment for Strido in MuJoCo.

Designed for sim-to-real on hobby servos, which report no position or velocity:
the observation only holds what the real robot measures or knows.

  observation (23): IMU gyro (3), gravity in the base frame from the IMU quaternion (3),
                    command vx, vy, wz (3), previous action (12), gait clock sin/cos (2)
  action (12):      joint offsets in [-1, 1] x ACTION_SCALE around the stand pose, Go2 order;
                    clamped like the firmware (joint limits + knee-crank window) before
                    they reach the position servos
  control:          50 Hz policy, 500 Hz physics; servo model = MJCF position actuators
                    (kp/kv, 3.43 N·m torque limit = SPT5435LV stall torque at 6 V)

Domain randomisation per episode: contact friction (floor and feet), servo stiffness, base mass, IMU noise.
"""

import math
from typing import Any, ClassVar

import gymnasium as gym
import mujoco
import numpy as np

from strido.gait import clamp_leg, stand_pose
from strido.geometry import LEG_NAMES
from strido.policy import ACTION_SCALE, COMMAND_RANGES, CONTROL_DT, GAIT_PERIOD_S, OBSERVATION_SIZE, slew_limit

from ..assets import SCENE

EPISODE_STEPS = 1000  # 20 s
MIN_HEIGHT_M = 0.09
MAX_TILT_COS = 0.6  # terminate beyond ~53 deg roll/pitch


def gravity_in_base(quaternion_wxyz) -> np.ndarray:
    rotation = np.zeros(9)
    mujoco.mju_quat2Mat(rotation, quaternion_wxyz)
    return rotation.reshape(3, 3).T @ np.array([0.0, 0.0, -1.0])


def clamp_targets(q: np.ndarray) -> np.ndarray:
    legs = q.reshape(4, 3)
    return np.concatenate([clamp_leg(name, tuple(leg)) for name, leg in zip(LEG_NAMES, legs)])


class StridoEnv(gym.Env):
    metadata: ClassVar[dict[str, Any]] = {"render_modes": ["rgb_array"], "render_fps": int(1 / CONTROL_DT)}

    def __init__(self, render_mode: str | None = None, randomise: bool = True, fixed_command=None):
        self.model = mujoco.MjModel.from_xml_path(str(SCENE))
        self.data = mujoco.MjData(self.model)
        self.render_mode = render_mode
        self.randomise = randomise
        self.fixed_command = None if fixed_command is None else np.asarray(fixed_command, dtype=float)
        self.substeps = round(CONTROL_DT / self.model.opt.timestep)
        self.default_q = stand_pose()
        self.nominal_kp = self.model.actuator_gainprm[:, 0].copy()
        self.nominal_mass = self.model.body_mass[1]
        self.nominal_friction = self.model.geom_friction[:, 0].copy()
        self.quat_adr = self.model.sensor_adr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SENSOR, "imu_quat")]
        self.gyro_adr = self.model.sensor_adr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SENSOR, "imu_gyro")]
        self.observation_space = gym.spaces.Box(-np.inf, np.inf, shape=(OBSERVATION_SIZE,), dtype=np.float32)
        self.action_space = gym.spaces.Box(-1.0, 1.0, shape=(12,), dtype=np.float32)
        self.renderer = None
        self.command = np.zeros(3)
        self.last_action = np.zeros(12)
        self.targets = self.default_q.copy()
        self.steps = 0

    def _sample_command(self) -> np.ndarray:
        if self.fixed_command is not None:
            return self.fixed_command.copy()
        if self.np_random.random() < 0.2:
            return np.zeros(3)
        return np.array([self.np_random.uniform(low, high) for low, high in COMMAND_RANGES])

    def _randomise(self) -> None:
        if not self.randomise:
            return
        scale = self.np_random.uniform(0.85, 1.15)
        self.model.actuator_gainprm[:, 0] = self.nominal_kp * scale
        self.model.actuator_biasprm[:, 1] = -self.nominal_kp * scale
        self.model.body_mass[1] = self.nominal_mass * self.np_random.uniform(0.9, 1.15)
        # MuJoCo uses the larger friction of the two contacting geoms: scale floor and feet together.
        self.model.geom_friction[:, 0] = self.nominal_friction * self.np_random.uniform(0.6, 1.2)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        mujoco.mj_resetData(self.model, self.data)
        self._randomise()
        self.data.qpos[2] = 0.185
        self.data.qpos[7:] = self.default_q + self.np_random.normal(0, 0.02, 12)
        self.data.ctrl[:] = self.default_q
        mujoco.mj_forward(self.model, self.data)
        self.targets = self.default_q.copy()
        self.command = self._sample_command()
        self.last_action = np.zeros(12)
        self.steps = 0
        return self._observation(), {}

    def _observation(self) -> np.ndarray:
        quaternion = self.data.sensordata[self.quat_adr : self.quat_adr + 4]
        gyro = self.data.sensordata[self.gyro_adr : self.gyro_adr + 3]
        gravity = gravity_in_base(quaternion)
        if self.randomise:
            gyro = gyro + self.np_random.normal(0, 0.05, 3)
            gravity = gravity + self.np_random.normal(0, 0.02, 3)
        phase = 2 * math.pi * (self.steps * CONTROL_DT / GAIT_PERIOD_S)
        return np.concatenate(
            [gyro, gravity, self.command, self.last_action, [math.sin(phase), math.cos(phase)]]
        ).astype(np.float32)

    def step(self, action):
        action = np.clip(np.asarray(action, dtype=float), -1.0, 1.0)
        # firmware order: slew limit, then joint and knee-crank clamp
        self.targets = clamp_targets(slew_limit(self.default_q + ACTION_SCALE * action, self.targets))
        self.data.ctrl[:] = self.targets
        for _ in range(self.substeps):
            mujoco.mj_step(self.model, self.data)
        self.steps += 1
        reward, terms = self._reward(action)
        self.last_action = action
        quaternion = self.data.qpos[3:7]
        upright = -gravity_in_base(quaternion)[2]
        fallen = self.data.qpos[2] < MIN_HEIGHT_M or upright < MAX_TILT_COS
        if fallen:
            reward -= 2.0
        truncated = self.steps >= EPISODE_STEPS
        return self._observation(), float(reward), bool(fallen), bool(truncated), terms

    def _reward(self, action):
        quaternion = self.data.qpos[3:7]
        rotation = np.zeros(9)
        mujoco.mju_quat2Mat(rotation, quaternion)
        rotation = rotation.reshape(3, 3)
        velocity_base = rotation.T @ self.data.qvel[0:3]
        angular_base = rotation.T @ self.data.qvel[3:6]
        tracking_xy = math.exp(-float(np.sum((velocity_base[:2] - self.command[:2]) ** 2)) / 0.01)
        tracking_yaw = math.exp(-float((angular_base[2] - self.command[2]) ** 2) / 0.05)
        vertical = float(velocity_base[2] ** 2)
        wobble = float(np.sum(angular_base[:2] ** 2))
        action_rate = float(np.sum((action - self.last_action) ** 2))
        torque = float(np.sum(self.data.actuator_force**2))
        height = float(self.data.qpos[2])
        terms = {
            "tracking_xy": tracking_xy,
            "tracking_yaw": tracking_yaw,
            "vx": float(velocity_base[0]),
            "height": height,
        }
        reward = (
            1.0 * tracking_xy
            + 0.8 * tracking_yaw
            - 2.0 * vertical
            - 0.05 * wobble
            - 0.01 * action_rate
            - 0.002 * torque
            - 2.0 * max(0.0, 0.15 - height)
        )
        return reward * CONTROL_DT * 50.0, terms  # at most 1.8 per step (perfect xy + yaw tracking)

    def render(self):
        if self.renderer is None:
            self.renderer = mujoco.Renderer(self.model, 480, 640)
        camera = mujoco.MjvCamera()
        camera.type = mujoco.mjtCamera.mjCAMERA_TRACKING
        camera.trackbodyid = 1
        camera.distance, camera.azimuth, camera.elevation = 0.9, 135.0, -20.0
        self.renderer.update_scene(self.data, camera)
        return self.renderer.render()

    def close(self):
        if self.renderer is not None:
            self.renderer.close()
            self.renderer = None
