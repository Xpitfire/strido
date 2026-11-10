"""strido-cli against a fake controller on a pseudo-terminal (POSIX)."""

import os
import struct
import threading
import tty

import pytest

from strido import cli, protocol

pytestmark = pytest.mark.skipif(not hasattr(os, "openpty"), reason="needs a POSIX pseudo-terminal")


class FakeController:
    """Answers REQUEST_CALIBRATION and records every frame the host sends."""

    def __init__(self, status=protocol.FLAG_PWM_OK | protocol.FLAG_CALIBRATION_MODE):
        self.status = status  # flags reported in STATE replies to raw-pulse commands
        self.master, self.slave = os.openpty()
        tty.setraw(self.slave)  # a USB CDC port never echoes; a fresh pty does
        self.port = os.ttyname(self.slave)
        self.frames = []
        self.running = True
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        reader = protocol.FrameReader()
        while self.running:
            try:
                data = os.read(self.master, 4096)
            except OSError:
                return
            for message_type, payload in reader.feed(data):
                self.frames.append((message_type, payload))
                if message_type == protocol.SERVO_PULSE_COMMAND:
                    state = protocol.State(
                        0, 0, self.status, (0.0,) * 12, (1.0, 0.0, 0.0, 0.0), (0.0,) * 3, (0.0,) * 3, 7.4, 0.5
                    )
                    os.write(self.master, protocol.encode_frame(protocol.STATE, state.pack()))
                if message_type == protocol.REQUEST_CALIBRATION:
                    for joint in range(12):
                        record = protocol.Calibration(joint, 1, 1500, 0.0, 600, 2400)
                        os.write(self.master, protocol.encode_frame(protocol.CALIBRATION, record.pack()))

    def close(self):
        self.running = False
        os.close(self.slave)  # wakes the reader (EIO on the master), closing the master first would block on macOS
        self.thread.join(timeout=2.0)
        os.close(self.master)


def test_calibrate_trims_saves_and_relaxes_on_exit(monkeypatch):
    controller = FakeController()
    answers = iter(["+", "++", ""] + [""] * 11)  # FL_hip: +5 then +25 µs, accept; all others unchanged
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    link = cli.Link(controller.port)
    cli.cmd_calibrate(link, None)
    link.close()
    threading.Event().wait(0.3)  # let the reader thread drain the pty
    controller.close()
    sets = [protocol.Calibration.unpack(p) for t, p in controller.frames if t == protocol.SET_CALIBRATION]
    assert len(sets) == 12 and sets[0].neutral_us == 1530 and all(s.neutral_us == 1500 for s in sets[1:])
    assert sum(1 for t, _ in controller.frames if t == protocol.SAVE_CALIBRATION) == 1
    last_type, last_payload = controller.frames[-1]
    assert last_type == protocol.JOINT_COMMAND and struct.unpack("<HB", last_payload[:3])[1] == protocol.MODE_RELAX


def test_center_refuses_when_the_controller_keeps_the_servos_relaxed():
    controller = FakeController(status=protocol.FLAG_RELAXED | protocol.FLAG_ESTOP)
    link = cli.Link(controller.port)
    with pytest.raises(SystemExit, match="not driving"):
        cli.cmd_center(link, None)
    link.close()
    controller.close()
