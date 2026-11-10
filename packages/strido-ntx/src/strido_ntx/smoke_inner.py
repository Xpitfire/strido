"""Checks run *inside* the NT-X environment by `strido_ntx.smoke` (exit 1 on the first failure).

1. the extension's assets are in the NT-X catalog (robot spec validates, skill loads);
2. the robot compiles into an NT-X MuJoCo world and stands for 2 s on the default posture;
3. the `strido-serial` robot adapter is registered;
4. the serial RobotPort drives a protocol-level fake MCU with the real `pd-pose` runtime output
   (gains + gravity feed-forward): command, state, sequence echo, IMU loss fails closed,
   protective stop, close.
"""

import math
import sys

import numpy as np
from ntx.core.contracts import JointCommand
from ntx.core.ports import PolicyCommand
from ntx.core.registry import registry
from ntx.embodiment.catalog import load_robot, load_scene
from ntx.sim.world import MujocoWorld
from ntx.skills.runtimes.pd_pose import PdPosePolicy
from ntx.skills.spec import load_skill

from strido import protocol

from .fake_mcu import FakeMcu
from .serial_port import ImuUnavailableError, StridoSerialPort

STAND_SECONDS = 2.0
MIN_BASE_HEIGHT_M = 0.12
MAX_TILT_DEG = 10.0


def check(condition: bool, message: str) -> None:
    print(f"{'ok  ' if condition else 'FAIL'} {message}")
    if not condition:
        sys.exit(1)


def tilt_deg(quat_wxyz: tuple[float, float, float, float]) -> float:
    _w, x, y, _z = quat_wxyz
    up_z = 1.0 - 2.0 * (x * x + y * y)  # z component of the body z axis in the world
    return math.degrees(math.acos(max(-1.0, min(1.0, up_z))))


def main() -> None:
    robot = load_robot("strido")
    check(
        robot.dof == 12 and robot.family == "quadruped",
        f"catalog robot strido: {robot.dof} joints, {robot.mass_kg} kg",
    )
    skill = load_skill("strido-stand")
    check(skill.robot_ids == ["strido"], f"catalog skill {skill.id} ({skill.runtime.name})")

    world = MujocoWorld(robot, load_scene(skill.default_scene))
    command = JointCommand(q=[j.default for j in robot.joints])
    world.reset(q=np.array(command.q))
    substeps = max(1, round(0.02 / world.physics_dt))
    for _ in range(round(STAND_SECONDS / 0.02)):
        world.step(command, substeps)
    state = world.state()
    height, tilt = state.base_pos[2], tilt_deg(state.base_quat)
    check(
        height > MIN_BASE_HEIGHT_M and tilt < MAX_TILT_DEG,
        f"stands in NT-X MuJoCo for {STAND_SECONDS:.0f} s: base {height:.3f} m, tilt {tilt:.1f} deg (model {world.model_sha256[:12]})",
    )

    robots = {entry["name"] for entry in registry.describe("robot")["robot"]}
    check("strido-serial" in robots, f"registry robot adapters: {sorted(robots)}")

    mcu = FakeMcu()
    port = StridoSerialPort(robot, mcu)
    port.apply(JointCommand(q=[j.default for j in robot.joints]))
    policy = PdPosePolicy(skill, robot)
    policy.reset(port.read_state())
    output = policy.act(port.read_state(), PolicyCommand())
    gravity_nm = max(abs(v) for v in output.command.tau_ff or [0.0])
    port.apply(output.command)  # kp/kd/tau_ff from the runtime: positive gains accepted, feed-forward dropped
    observed = port.read_state()
    check(
        np.allclose(observed.q, output.command.q, atol=1e-5) and observed.seq == 2 and not port.has_odometry,
        f"serial port: pd-pose output (|tau_ff| up to {gravity_nm:.2f} N m) -> MCU -> state "
        f"(q[1]={observed.q[1]:.3f} rad, seq {observed.seq})",
    )
    mcu.imu_ok = False
    mcu.publish_state()
    try:
        port.read_state()
        imu_failed_closed = False
    except ImuUnavailableError:
        imu_failed_closed = mcu.estop
    check(imu_failed_closed, "serial port: a state without IMU raises and latches the protective stop")
    port.protective_stop()
    check(mcu.estop and mcu.frames[-1][0] == protocol.ESTOP, "serial port: protective stop latches the MCU e-stop")
    port.close()
    check(mcu.closed, "serial port: close releases the device")
    print("ntx-smoke: Strido extension works inside NT-X")


if __name__ == "__main__":
    main()
