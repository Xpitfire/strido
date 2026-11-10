"""In-memory stand-in for the ESP32-S3 motion controller (tests and the NT-X smoke run).

Speaks the real wire protocol: decodes host frames, applies the e-stop latch like the
firmware, and answers every frame with a STATE frame that echoes the target and the
sequence number of the last joint command (like the firmware's `last_command_seq`).
"""

from strido import protocol

UPRIGHT_WXYZ = (1.0, 0.0, 0.0, 0.0)


class FakeMcu:
    """Byte-level `Transport` double: write() consumes host frames, read() returns MCU frames."""

    def __init__(self, bus_voltage: float = 7.6) -> None:
        self._reader = protocol.FrameReader()
        self._outbox = bytearray()
        self.bus_voltage = bus_voltage
        self.estop = False
        self.q = [0.0] * 12
        self.time_ms = 0
        self.closed = False
        self.imu_ok = True
        self.last_command_seq = 0
        self.frames: list[tuple[int, bytes]] = []

    def write(self, data: bytes) -> int:
        for message_type, payload in self._reader.feed(data):
            self.frames.append((message_type, payload))
            if message_type == protocol.ESTOP:
                self.estop = bool(payload[0])
            elif message_type == protocol.JOINT_COMMAND and not self.estop:
                seq, _mode, q = protocol.decode_joint_command(payload)
                self.last_command_seq, self.q = seq, list(q)
            self.publish_state()
        return len(data)

    def publish_state(self) -> None:
        self.time_ms += 10
        status = protocol.FLAG_POWER_OK | protocol.FLAG_PWM_OK | (protocol.FLAG_IMU_OK if self.imu_ok else 0)
        if self.estop:
            status |= protocol.FLAG_ESTOP
        state = protocol.State(
            self.last_command_seq,
            self.time_ms,
            status,
            tuple(self.q),
            UPRIGHT_WXYZ,
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 9.81),
            self.bus_voltage,
            1.2,
        )
        self._outbox += protocol.encode_frame(protocol.STATE, state.pack())

    def read(self, size: int) -> bytes:
        chunk = bytes(self._outbox[:size])
        del self._outbox[:size]
        return chunk

    def close(self) -> None:
        self.closed = True
