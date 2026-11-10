"""NT-X `RobotPort` for a physical Strido over the ESP32-S3 USB link.

Semantics (NT-X developer guide, "new transport" checklist):

* clock: `t` is the MCU uptime of the last state frame; `stamp_ns` the host monotonic receive time;
* measured: base orientation and body rates (IMU); NOT measured: joint positions (hobby servos
  report nothing, `q` is the clamped command the MCU applies), joint velocity/torque, base
  position and linear velocity (`has_odometry` False);
* freshness: every poll drains the input buffer, so the newest frame wins; `read_state` raises
  `TimeoutError` if no state frame arrived within `state_timeout_s` (first state included);
  a state older than that is never returned;
* fail closed: a state without a working IMU latches the protective stop and raises
  `ImuUnavailableError` (the base orientation would otherwise read as level);
* `apply` sends one position target; `hold` re-sends the last target (the MCU watchdog holds
  the pose 200 ms after the last command and relaxes the servos 2 s later);
* `protective_stop` latches the MCU e-stop (PCA9685 OE high: every servo pulse stops at once);
  hobby servos cannot damp, so a stopped robot goes limp - park it in the rest pose first;
* `release` clears the e-stop, `close` stops and frees the serial device (exclusive owner);
* the codec (`strido_ntx.codec`) is separate from the transport (`Transport`).
"""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import serial
from ntx.core.contracts import JointCommand, RobotSpec, RobotState, StateSource

from strido import protocol

from . import codec

READ_CHUNK_BYTES = 4096
MAX_DRAIN_CHUNKS = 64  # 256 KiB per poll: ~20 s of the MCU's ~11 KB/s state stream
POLL_SLEEP_S = 0.001


class ImuUnavailableError(RuntimeError):
    """The MCU reports no IMU: orientation and body rates are unknown, the protective stop is latched."""


class Transport(Protocol):
    """Byte pipe to the MCU (pyserial `Serial` satisfies it)."""

    def write(self, data: bytes) -> int | None: ...

    def read(self, size: int) -> bytes: ...

    def close(self) -> None: ...


def open_serial(device: str) -> Transport:
    port = serial.Serial(device, 115200, timeout=0, exclusive=True)  # USB CDC ignores the baud rate
    port.reset_input_buffer()  # frames queued before the session are stale
    transport: Transport = port
    return transport


@dataclass
class _Latest:
    state: codec.DecodedState
    received_ns: int


class StridoSerialPort:
    """`ntx.core.ports.RobotPort` implementation for Strido hardware."""

    def __init__(
        self,
        spec: RobotSpec,
        transport: Transport,
        state_timeout_s: float = 0.2,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        if spec.dof != codec.JOINT_COUNT:
            raise ValueError(f"{spec.id}: expected {codec.JOINT_COUNT} joints, spec has {spec.dof}")
        self._spec = spec
        self._transport = transport
        self._timeout_ns = int(state_timeout_s * 1e9)
        self._clock_ns = clock_ns
        self._reader = protocol.FrameReader()
        self._latest: _Latest | None = None
        self._seq = 0
        self._last_q: list[float] | None = None
        self._lower = [j.lower for j in spec.joints]
        self._upper = [j.upper for j in spec.joints]
        self._closed = False

    # ------------------------------------------------------------------ RobotPort properties
    @property
    def spec(self) -> RobotSpec:
        return self._spec

    @property
    def source(self) -> StateSource:
        return StateSource.HARDWARE

    @property
    def has_odometry(self) -> bool:
        return False

    # ------------------------------------------------------------------ state
    def _poll(self) -> None:
        for _ in range(MAX_DRAIN_CHUNKS):
            data = self._transport.read(READ_CHUNK_BYTES)
            if not data:
                return
            for message_type, payload in self._reader.feed(data):
                if message_type == protocol.STATE and len(payload) == protocol.STATE_PAYLOAD_SIZE:
                    self._latest = _Latest(codec.decode_state(payload), self._clock_ns())

    def read_state(self) -> RobotState:
        deadline = self._clock_ns() + self._timeout_ns
        while True:
            self._poll()
            now = self._clock_ns()
            if self._latest is not None and now - self._latest.received_ns <= self._timeout_ns:
                return self._to_record(self._latest)
            if now >= deadline:
                raise TimeoutError(f"{self._spec.id}: no MCU state for {self._timeout_ns / 1e9:.3f} s")
            time.sleep(POLL_SLEEP_S)

    def _to_record(self, latest: _Latest) -> RobotState:
        state = latest.state
        if not state.imu_ok:
            self.protective_stop()
            raise ImuUnavailableError(f"{self._spec.id}: MCU reports no IMU; protective stop latched")
        return RobotState(
            robot_id=self._spec.id,
            seq=state.command_seq,
            t=state.mcu_time_s,
            stamp_ns=latest.received_ns,
            source=StateSource.HARDWARE,
            base_pos=(0.0, 0.0, 0.0),
            base_quat=state.base_quat,
            base_lin_vel=(0.0, 0.0, 0.0),
            base_ang_vel=state.base_ang_vel,
            q=list(state.q),
            dq=[0.0] * codec.JOINT_COUNT,
        )

    # ------------------------------------------------------------------ commands
    def _next_seq(self) -> int:
        self._seq = (self._seq + 1) & 0xFFFF
        return self._seq

    def apply(self, command: JointCommand) -> None:
        if self._closed:
            raise RuntimeError(f"{self._spec.id}: port is closed")
        q = [min(max(value, low), high) for value, low, high in zip(command.q, self._lower, self._upper, strict=True)]
        if not all(math.isfinite(v) for v in command.q):
            self.protective_stop()
            raise codec.CommandRejectedError("non-finite joint target: protective stop latched")
        frame = codec.encode_joint_command(self._next_seq(), q, command.dq, command.kp)
        self._transport.write(frame)
        self._last_q = q

    def hold(self) -> None:
        if self._last_q is not None and not self._closed:
            self._transport.write(codec.encode_joint_command(self._next_seq(), self._last_q))

    def protective_stop(self) -> None:
        if not self._closed:
            self._transport.write(codec.encode_stop())

    def release(self) -> None:
        if not self._closed:
            self._transport.write(codec.encode_release())

    def close(self) -> None:
        if self._closed:
            return
        self.protective_stop()
        self._closed = True
        self._transport.close()
