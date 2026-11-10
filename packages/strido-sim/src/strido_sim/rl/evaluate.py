"""Evaluate an exported policy (policy.npz) in MuJoCo with fixed commands; optional video.

    python -m strido_sim.rl.evaluate build/rl/<run>/policy.npz --vx 0.2 --seconds 10
    python -m strido_sim.rl.evaluate build/rl/<run>/policy.npz --video build/rl/eval.mp4

Uses the same numpy forward pass as the robot (strido.policy), so a policy that walks
here is exactly the function the robot will run.
"""

import argparse
import math
from pathlib import Path

import imageio.v2 as imageio
import numpy as np

from strido.policy import MlpPolicy

from .env import CONTROL_DT, StridoEnv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("policy")
    parser.add_argument("--vx", type=float, default=0.2)
    parser.add_argument("--vy", type=float, default=0.0)
    parser.add_argument("--wz", type=float, default=0.0)
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--video", default=None)
    args = parser.parse_args()
    policy = MlpPolicy.load(args.policy)
    env = StridoEnv(randomise=False, fixed_command=(args.vx, args.vy, args.wz))
    observation, _ = env.reset(seed=0)
    frames, vx_log, fallen = [], [], False
    start = env.data.qpos[:2].copy()
    for _ in range(int(args.seconds / CONTROL_DT)):
        observation, _, terminated, _truncated, info = env.step(policy(observation))
        vx_log.append(info["vx"])
        if args.video:
            frames.append(env.render())
        if terminated:
            fallen = True
            break
    distance = env.data.qpos[:2] - start
    w, x, y, z = env.data.qpos[3:7]
    yaw = math.degrees(math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))
    print(
        f"fallen={fallen} distance x={distance[0]:.3f} m y={distance[1]:.3f} m mean vx={np.mean(vx_log):.3f} m/s "
        f"(command {args.vx}, {args.vy}, {args.wz}) height={env.data.qpos[2]:.3f} m yaw={yaw:.1f} deg (wrapped)"
    )
    if args.video:
        Path(args.video).parent.mkdir(parents=True, exist_ok=True)
        imageio.mimsave(args.video, frames, fps=int(1 / CONTROL_DT))
        print(f"video -> {args.video}")


if __name__ == "__main__":
    main()
