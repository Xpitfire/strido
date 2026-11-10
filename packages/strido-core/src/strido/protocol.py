"""Host side of the Strido MCU protocol (mirror of firmware protocol.h/.cpp).

Wire format: COBS(type | payload | crc16_le) + 0x00. CRC-16/CCITT-FALSE.
See docs/software.md ("Protocol").
"""

import struct
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

JOINT_COMMAND = 0x01
SERVO_PULSE_COMMAND = 0x02
SET_CALIBRATION = 0x03
SAVE_CALIBRATION = 0x04
REQUEST_CALIBRATION = 0x05
ESTOP = 0x06
DISPLAY = 0x07
STATE = 0x81
CALIBRATION = 0x82
LOG = 0x83

MODE_RELAX = 0
MODE_POSITION = 1

FLAG_ESTOP = 1 << 0
FLAG_RELAXED = 1 << 1
FLAG_WATCHDOG = 1 << 2
FLAG_IMU_OK = 1 << 3
FLAG_POWER_OK = 1 << 4
FLAG_PWM_OK = 1 << 5
FLAG_CLAMPED = 1 << 6
FLAG_CALIBRATION_MODE = 1 << 7

_JOINT_COMMAND = struct.Struct("<HB12f")
_SERVO_PULSE = struct.Struct("<H12H")
_CALIBRATION = struct.Struct("<BbHfHH")
_STATE = struct.Struct("<HIB12f4f3f3fff")


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def cobs_encode(data: bytes) -> bytes:
    output = bytearray(b"\x00")
    code_index = 0
    code = 1
    for byte in data:
        if byte == 0:
            output[code_index] = code
            code_index = len(output)
            output.append(0)
            code = 1
        else:
            output.append(byte)
            code += 1
            if code == 0xFF:
                output[code_index] = code
                code_index = len(output)
                output.append(0)
                code = 1
    output[code_index] = code
    return bytes(output)


def cobs_decode(data: bytes) -> bytes:
    output = bytearray()
    index = 0
    while index < len(data):
        code = data[index]
        if code == 0:
            raise ValueError("zero byte inside COBS frame")
        index += 1
        block = data[index : index + code - 1]
        if len(block) != code - 1 or 0 in block:
            raise ValueError("truncated COBS frame")
        output += block
        index += code - 1
        if code != 0xFF and index < len(data):
            output.append(0)
    return bytes(output)


def encode_frame(message_type: int, payload: bytes = b"") -> bytes:
    packet = bytes([message_type]) + payload
    packet += struct.pack("<H", crc16(packet))
    return cobs_encode(packet) + b"\x00"


def parse_packet(packet: bytes) -> tuple[int, bytes]:
    if len(packet) < 3:
        raise ValueError("packet too short")
    (expected,) = struct.unpack("<H", packet[-2:])
    if crc16(packet[:-2]) != expected:
        raise ValueError("CRC mismatch")
    return packet[0], packet[1:-2]


class FrameReader:
    """Accumulates bytes and yields decoded (type, payload) tuples."""

    MAX_FRAME = 400

    def __init__(self) -> None:
        self._buffer = bytearray()
        self.dropped = 0

    def feed(self, data: bytes) -> Iterator[tuple[int, bytes]]:
        for byte in data:
            if byte != 0:
                if len(self._buffer) < self.MAX_FRAME:
                    self._buffer.append(byte)
                continue
            if self._buffer:
                try:
                    yield parse_packet(cobs_decode(bytes(self._buffer)))
                except ValueError:
                    self.dropped += 1
            self._buffer.clear()


def joint_command(seq: int, mode: int, q: Sequence[float]) -> bytes:
    assert len(q) == 12
    return encode_frame(JOINT_COMMAND, _JOINT_COMMAND.pack(seq & 0xFFFF, mode, *map(float, q)))


def decode_joint_command(payload: bytes) -> tuple[int, int, tuple[float, ...]]:
    """(seq, mode, 12 joint angles) of a JOINT_COMMAND payload (MCU side; used by test doubles)."""
    values = _JOINT_COMMAND.unpack(payload)
    return int(values[0]), int(values[1]), tuple(float(v) for v in values[2:])


def servo_pulse_command(seq: int, pulses_us: Sequence[int]) -> bytes:
    assert len(pulses_us) == 12
    return encode_frame(SERVO_PULSE_COMMAND, _SERVO_PULSE.pack(seq & 0xFFFF, *map(int, pulses_us)))


@dataclass
class Calibration:
    joint: int
    direction: int
    neutral_us: int
    zero_rad: float
    min_us: int
    max_us: int

    def pack(self) -> bytes:
        return _CALIBRATION.pack(self.joint, self.direction, self.neutral_us, self.zero_rad, self.min_us, self.max_us)

    @classmethod
    def unpack(cls, payload: bytes) -> "Calibration":
        return cls(*_CALIBRATION.unpack(payload))


def set_calibration(calibration: Calibration) -> bytes:
    return encode_frame(SET_CALIBRATION, calibration.pack())


def estop(engaged: bool) -> bytes:
    return encode_frame(ESTOP, bytes([1 if engaged else 0]))


def display(expression: int, text: str = "") -> bytes:
    raw = text.encode("ascii", "replace")[:32]
    return encode_frame(DISPLAY, bytes([expression, len(raw)]) + raw)


@dataclass
class State:
    last_command_seq: int
    time_ms: int
    status: int
    q: tuple[float, ...]
    quat_wxyz: tuple[float, ...]
    gyro: tuple[float, ...]
    accel: tuple[float, ...]
    bus_voltage: float
    current: float

    @classmethod
    def unpack(cls, payload: bytes) -> "State":
        values = _STATE.unpack(payload)
        return cls(
            last_command_seq=values[0],
            time_ms=values[1],
            status=values[2],
            q=values[3:15],
            quat_wxyz=values[15:19],
            gyro=values[19:22],
            accel=values[22:25],
            bus_voltage=values[25],
            current=values[26],
        )

    def pack(self) -> bytes:
        return _STATE.pack(
            self.last_command_seq,
            self.time_ms,
            self.status,
            *self.q,
            *self.quat_wxyz,
            *self.gyro,
            *self.accel,
            self.bus_voltage,
            self.current,
        )


STATE_PAYLOAD_SIZE = _STATE.size
