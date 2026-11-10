"""Strido in MuJoCo: stand up and trot from velocity commands.

Examples (from the repository root, after `make setup`):
    make sim-walk
    uv run --locked python -m strido_sim.walk --video build/sim/walk.mp4 --seconds 8
    uv run --locked mjpython -m strido_sim.walk --viewer      # macOS needs mjpython for the viewer
Viewer keys: arrow up/down = vx, left/right = yaw rate, space = stop.

The gait is `strido.gait` - the same code that drives the real
robot through ROS 2 - so what walks here is what the robot will be commanded.
"""

import argparse
import math
import time
from pathlib import Path

import imageio.v3 as iio
import mujoco
import mujoco.viewer
import numpy as np

from strido.gait import GaitConfig, TrotGait, stand_pose

from .assets import SCENE

CONTROL_DT = 0.01  # 100 Hz, the rate of the real joint command stream


def yaw_of(quaternion) -> float:
    w, x, y, z = quaternion
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


class Simulation:
    def __init__(self, heading_hold: bool = True):
        self.model = mujoco.MjModel.from_xml_path(str(SCENE))
        self.data = mujoco.MjData(self.model)
        self.gait = TrotGait(GaitConfig())
        self.heading_hold = heading_hold
        self.heading = 0.0
        self.command = np.zeros(3)
        q0 = stand_pose()
        self.data.qpos[2] = 0.185
        self.data.qpos[7:] = q0
        self.data.ctrl[:] = q0
        mujoco.mj_forward(self.model, self.data)
        self.substeps = round(CONTROL_DT / self.model.opt.timestep)

    def set_command(self, vx, vy, wz):
        self.command = np.array([vx, vy, wz], dtype=float)

    def step(self):
        yaw = yaw_of(self.data.qpos[3:7])
        wz = self.command[2]
        if self.heading_hold and abs(wz) < 1e-3 and np.linalg.norm(self.command[:2]) > 1e-3:
            wz = float(np.clip(-2.0 * math.remainder(yaw - self.heading, 2 * math.pi), -0.5, 0.5))
        else:
            self.heading = yaw
        self.gait.set_command(self.command[0], self.command[1], wz)
        self.data.ctrl[:] = self.gait.step(CONTROL_DT)
        for _ in range(self.substeps):
            mujoco.mj_step(self.model, self.data)

    @property
    def base_position(self):
        return self.data.qpos[:3].copy()


def run_headless(args):
    sim = Simulation()
    for _ in range(int(1.0 / CONTROL_DT)):
        sim.step()  # settle
    start = sim.base_position
    sim.set_command(args.vx, args.vy, args.wz)
    renderer = frames = None
    if args.video:
        renderer = mujoco.Renderer(sim.model, height=540, width=960)
        frames = []
        camera = mujoco.MjvCamera()
        camera.type = mujoco.mjtCamera.mjCAMERA_TRACKING
        camera.trackbodyid = sim.model.body("base_link").id
        camera.distance, camera.azimuth, camera.elevation = 0.9, 135.0, -20.0
    steps = int(args.seconds / CONTROL_DT)
    for k in range(steps):
        sim.step()
        if renderer is not None and k % 3 == 0:
            renderer.update_scene(sim.data, camera)
            frames.append(renderer.render())
    end = sim.base_position
    distance = end - start
    print(
        f"commanded vx={args.vx} vy={args.vy} wz={args.wz} for {args.seconds:.1f}s -> displacement "
        f"{np.round(distance, 3).tolist()} m, base height {end[2]:.3f} m, yaw {math.degrees(yaw_of(sim.data.qpos[3:7])):.1f} deg"
    )
    if frames:
        Path(args.video).parent.mkdir(parents=True, exist_ok=True)
        iio.imwrite(args.video, np.stack(frames), fps=int(1 / (3 * CONTROL_DT)), codec="libx264")
        print(f"video -> {args.video}")
    return distance


def run_viewer(args):
    sim = Simulation()
    command = np.array([0.0, 0.0, 0.0])

    def on_key(key):
        if key == 265:
            command[0] = min(command[0] + 0.05, 0.3)
        elif key == 264:
            command[0] = max(command[0] - 0.05, -0.3)
        elif key == 263:
            command[2] = min(command[2] + 0.2, 1.0)
        elif key == 262:
            command[2] = max(command[2] - 0.2, -1.0)
        elif key == 32:
            command[:] = 0.0

    with mujoco.viewer.launch_passive(sim.model, sim.data, key_callback=on_key) as viewer:
        while viewer.is_running():
            tick = time.perf_counter()
            sim.set_command(*command)
            sim.step()
            viewer.sync()
            time.sleep(max(0.0, CONTROL_DT - (time.perf_counter() - tick)))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--viewer", action="store_true")
    parser.add_argument("--seconds", type=float, default=8.0)
    parser.add_argument("--vx", type=float, default=0.15)
    parser.add_argument("--vy", type=float, default=0.0)
    parser.add_argument("--wz", type=float, default=0.0)
    parser.add_argument("--video", type=str, default="")
    args = parser.parse_args()
    if args.viewer:
        run_viewer(args)
    else:
        run_headless(args)


if __name__ == "__main__":
    main()
