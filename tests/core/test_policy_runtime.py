"""Numpy policy runtime: the exact function the robot runs (no torch on the Pi)."""

import numpy as np
import pytest

from strido import policy
from strido.workspace import path

RELEASED = path("models/policies/ppo-v1/policy.npz")


def test_released_policy_maps_an_observation_to_bounded_joint_actions():
    runtime = policy.MlpPolicy.load(RELEASED)
    observation = np.zeros(policy.OBSERVATION_SIZE)
    observation[5] = -1.0  # gravity straight down in the base frame: robot level
    action = runtime(observation)
    assert action.shape == (12,) and np.all(np.abs(action) <= 1.0)
    extreme = runtime(np.full(policy.OBSERVATION_SIZE, 1e6))  # normalisation clips wild inputs
    assert np.all(np.isfinite(extreme)) and np.all(np.abs(extreme) <= 1.0)


def test_policy_trained_with_another_observation_layout_is_refused(tmp_path):
    weights = dict(np.load(RELEASED))
    weights["obs_mean"] = np.zeros(policy.OBSERVATION_SIZE + 3, dtype=np.float32)
    broken = tmp_path / "policy.npz"
    np.savez(broken, **weights)
    with pytest.raises(AssertionError, match="observation layout"):
        policy.MlpPolicy.load(broken)


def test_commands_are_clipped_to_the_trained_ranges():
    clipped = policy.clip_command((1.0, -1.0, 0.1))
    assert clipped.tolist() == [policy.COMMAND_RANGES[0][1], policy.COMMAND_RANGES[1][0], 0.1]


def test_slew_limit_matches_the_firmware_speed_limit():
    previous = np.zeros(12)
    limited = policy.slew_limit(np.full(12, 1.0), previous)
    step = policy.MAX_JOINT_SPEED_RAD_S * policy.CONTROL_DT
    assert np.allclose(limited, step)
    assert np.allclose(policy.slew_limit(np.full(12, 0.01), previous), 0.01)
