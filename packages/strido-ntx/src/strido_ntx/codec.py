"""Codec between NT-X robot records and the Strido MCU wire protocol (no transport, no NT-X import).

NT-X speaks PD targets per joint (`JointCommand`: q, dq, kp, kd, tau_ff) and expects a
`RobotState` with measured base motion. Strido has hobby position servos without
feedback, so the mapping is deliberately lossy and explicit:

* command: only `q` is sent (MCU `JOINT_COMMAND`, position mode). Each servo closes its own
  position loop with a fixed stiffness, so positive `kp`/`kd` are accepted as "servo default"
  and `tau_ff` is dropped (the servo loop carries the static load NT-X's gravity feed-forward
  would cover). Requests the servos cannot honour are rejected (`unsupported_fields`): a
  non-zero joint velocity target, or `kp <= 0` (a limp joint; use `protective_stop`).
* state: `q` is the angle the MCU applies after its joint/linkage clamps (commanded, not
  measured); `dq` and `tau` are unknown (zeros / empty); the base orientation and body
  rates come from the IMU; base position and linear velocity are not measured
  (`has_odometry` is False on the port). NT-X therefore runs only gantry skills on this port
  until a base estimator exists (see docs/ntx-integration.md).

Joint order = MCU order = RobotSpec order: FL, FR, RL, RR x (hip, thigh, calf).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from strido import protocol

JOINT_COUNT = 12
FLAG_TEXT = {
    protocol.FLAG_ESTOP: "estop",
    protocol.FLAG_RELAXED: "relaxed",
    protocol.FLAG_WATCHDOG: "watchdog",
    protocol.FLAG_IMU_OK: "imu_ok",
    protocol.FLAG_POWER_OK: "power_ok",
    protocol.FLAG_PWM_OK: "pwm_ok",
    protocol.FLAG_CLAMPED: "clamped",
    protocol.FLAG_CALIBRATION_MODE: "calibration_mode",
}


class CommandRejectedError(ValueError):
    """A command the servos cannot execute faithfully (wrong size, non-finite, unsupported fields)."""


@dataclass(frozen=True)
class DecodedState:
    """MCU state mapped onto NT-X `RobotState` fields (SI units, quaternion w-first)."""

    mcu_time_s: float
    command_seq: int
    q: tuple[float, ...]
    base_quat: tuple[float, float, float, float]
    base_ang_vel: tuple[float, float, float]
    bus_voltage: float
    logic_current: float
    flags: frozenset[str]

    @property
    def imu_ok(self) -> bool:
        return "imu_ok" in self.flags

    @property
    def stopped(self) -> bool:
        return bool({"estop", "relaxed"} & self.flags)


def unsupported_fields(dq: Sequence[float] | None, kp: Sequence[float] | None) -> list[str]:
    """Command fields position servos cannot honour: a velocity target, or a zero/negative stiffness."""
    problems = []
    if dq is not None and any(abs(v) > 1e-9 for v in dq):
        problems.append("dq")
    if kp is not None and any(v <= 0.0 for v in kp):
        problems.append("kp <= 0")
    return problems


def encode_joint_command(
    seq: int, q: Sequence[float], dq: Sequence[float] | None = None, kp: Sequence[float] | None = None
) -> bytes:
    """Wire frame for one position target, or `CommandRejectedError` (`tau_ff`/`kd` are not taken)."""
    if len(q) != JOINT_COUNT:
        raise CommandRejectedError(f"expected {JOINT_COUNT} joint targets, got {len(q)}")
    if not all(math.isfinite(v) for v in q):
        raise CommandRejectedError("non-finite joint target")
    unsupported = unsupported_fields(dq, kp)
    if unsupported:
        raise CommandRejectedError(f"hobby servos cannot apply {', '.join(unsupported)}; send position targets only")
    return protocol.joint_command(seq, protocol.MODE_POSITION, [float(v) for v in q])


def encode_stop() -> bytes:
    """Latched protective stop: the MCU pulls PCA9685 OE high, every servo pulse stops (servos go limp)."""
    return protocol.estop(True)


def encode_release() -> bytes:
    return protocol.estop(False)


def decode_state(payload: bytes) -> DecodedState:
    if len(payload) != protocol.STATE_PAYLOAD_SIZE:
        raise ValueError(f"state payload has {len(payload)} bytes, expected {protocol.STATE_PAYLOAD_SIZE}")
    state = protocol.State.unpack(payload)
    flags = frozenset(name for bit, name in FLAG_TEXT.items() if state.status & bit)
    w, x, y, z = (float(v) for v in state.quat_wxyz)
    gx, gy, gz = (float(v) for v in state.gyro)
    return DecodedState(
        mcu_time_s=state.time_ms / 1000.0,
        command_seq=state.last_command_seq,
        q=tuple(float(v) for v in state.q),
        base_quat=(w, x, y, z),
        base_ang_vel=(gx, gy, gz),
        bus_voltage=float(state.bus_voltage),
        logic_current=float(state.current),
        flags=flags,
    )
