"""strido-cli: bench tool for the ESP32-S3 motion controller (no ROS needed).

    strido-cli center                 # 1500 µs on all 12 channels (assembly reference), Ctrl-C to stop
    strido-cli pulse FL_thigh 1600    # one joint, others off
    strido-cli calibrate              # interactive neutral trim per joint, saved to flash
    strido-cli monitor                # battery, flags, IMU at 2 Hz

The firmware holds the servos 200 ms after the last command and relaxes them 2 s later,
so every mode streams commands at 20 Hz in a background thread. The servo loop key must
be inserted for the servos to move. Raw pulses bypass the joint and knee-crank limits
(only the per-joint pulse window applies): use them with horns not yet fitted or the
legs free to move.
"""

import argparse
import math
import os
import threading
import time
from collections.abc import Iterator, Sequence

import serial

from . import protocol
from .geometry import LEG_NAMES

JOINTS = [f"{leg}_{joint}" for leg in LEG_NAMES for joint in ("hip", "thigh", "calf")]
CENTRE_US = 1500
STREAM_HZ = 20.0
TRIM_STEPS_US = {"+": 5, "-": -5, "++": 25, "--": -25}
DEFAULT_PORT = "/dev/strido_mcu"  # udev symlink from ros2/strido_bringup/config/99-strido.rules


class Link:
    """Serial connection that keeps streaming the current pulse set."""

    def __init__(self, port: str) -> None:
        self.serial = serial.Serial(port, 115200, timeout=0.05)  # USB CDC ignores the baud rate
        self.reader = protocol.FrameReader()
        self.pulses = [0] * 12
        self.seq = 0
        self.lock = threading.Lock()
        self.running = False
        self.thread: threading.Thread | None = None

    def start_stream(self) -> None:
        self.running = True
        thread = threading.Thread(target=self._stream, daemon=True)
        self.thread = thread
        thread.start()

    def _stream(self) -> None:
        while self.running:
            with self.lock:
                self.seq = (self.seq + 1) & 0xFFFF
                self.serial.write(protocol.servo_pulse_command(self.seq, self.pulses))
            time.sleep(1.0 / STREAM_HZ)

    def set_pulses(self, pulses: Sequence[int]) -> None:
        with self.lock:
            self.pulses = list(pulses)

    def send(self, frame: bytes) -> None:
        with self.lock:
            self.serial.write(frame)

    def messages(self, duration_s: float) -> Iterator[tuple[int, bytes]]:
        end = time.monotonic() + duration_s
        while time.monotonic() < end:
            data = self.serial.read(512)
            yield from self.reader.feed(data)

    def close(self) -> None:
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=1.0)
        self.serial.write(protocol.joint_command(self.seq + 1, protocol.MODE_RELAX, [0.0] * 12))  # outputs off
        self.serial.close()


def read_calibration(link: Link) -> dict[int, protocol.Calibration]:
    link.send(protocol.encode_frame(protocol.REQUEST_CALIBRATION))
    result = {}
    for message_type, payload in link.messages(1.0):
        if message_type == protocol.CALIBRATION:
            calibration = protocol.Calibration.unpack(payload)
            result[calibration.joint] = calibration
        if len(result) == 12:
            break
    assert len(result) == 12, f"controller returned {len(result)} of 12 calibration records"
    return result


def confirm_driving(link: Link) -> None:
    """Fail loudly if the controller is not putting out pulses (e-stop, battery, PCA9685 fault)."""
    status = None
    for message_type, payload in link.messages(0.5):
        if message_type == protocol.STATE:
            status = protocol.State.unpack(payload).status
    if status is None:
        raise SystemExit("no state from the controller: wrong port or firmware not running")
    if status & protocol.FLAG_RELAXED or not status & protocol.FLAG_CALIBRATION_MODE:
        raise SystemExit(
            f"controller is not driving the servos (status flags 0x{status:02x}): check e-stop, battery and PCA9685"
        )


def cmd_center(link: Link, args: argparse.Namespace) -> None:
    link.set_pulses([CENTRE_US] * 12)
    link.start_stream()
    confirm_driving(link)
    print("all channels at 1500 µs - fit horns now; Ctrl-C to release")
    while True:
        time.sleep(1.0)


def cmd_pulse(link: Link, args: argparse.Namespace) -> None:
    assert args.joint in JOINTS, f"joint must be one of {JOINTS}"
    assert 500 <= args.us <= 2500, "pulse must be 500..2500 µs"
    pulses = [0] * 12
    pulses[JOINTS.index(args.joint)] = args.us
    link.set_pulses(pulses)
    link.start_stream()
    confirm_driving(link)
    print(f"{args.joint} at {args.us} µs; Ctrl-C to release")
    while True:
        time.sleep(1.0)


def cmd_calibrate(link: Link, args: argparse.Namespace) -> None:
    calibration = read_calibration(link)
    pulses = [record.neutral_us for _, record in sorted(calibration.items())]
    link.set_pulses(pulses)
    link.start_stream()
    print("Robot on a stand. All joints at their neutral pulse (assembly reference pose).")
    print("Per joint: '+'/'-' = ±5 µs, '++'/'--' = ±25 µs, Enter = accept, 'q' = abort without saving.")
    for joint, name in enumerate(JOINTS):
        record = calibration[joint]
        while True:
            answer = input(f"{name:10s} neutral {record.neutral_us} µs > ").strip()
            if answer == "q":
                print("aborted, nothing saved")
                return
            if answer == "":
                break
            if answer not in TRIM_STEPS_US:
                print("use + - ++ -- Enter or q")
                continue
            record.neutral_us = max(record.min_us, min(record.max_us, record.neutral_us + TRIM_STEPS_US[answer]))
            pulses[joint] = record.neutral_us
            link.set_pulses(pulses)
        link.send(protocol.set_calibration(record))
    link.send(protocol.encode_frame(protocol.SAVE_CALIBRATION))
    print("calibration saved to the controller flash")


def cmd_monitor(link: Link, args: argparse.Namespace) -> None:
    flags = {
        protocol.FLAG_ESTOP: "ESTOP",
        protocol.FLAG_RELAXED: "relaxed",
        protocol.FLAG_WATCHDOG: "watchdog",
        protocol.FLAG_IMU_OK: "imu",
        protocol.FLAG_POWER_OK: "power",
        protocol.FLAG_PWM_OK: "pwm",
        protocol.FLAG_CLAMPED: "clamped",
        protocol.FLAG_CALIBRATION_MODE: "calibration",
    }
    last_print = 0.0
    while True:
        for message_type, payload in link.messages(0.1):
            if message_type == protocol.LOG:
                print("mcu:", payload.decode("ascii", "replace"))
            if message_type != protocol.STATE or time.monotonic() - last_print < 0.5:
                continue
            last_print = time.monotonic()
            state = protocol.State.unpack(payload)
            active = " ".join(name for bit, name in flags.items() if state.status & bit)
            w, x, y, z = state.quat_wxyz
            roll = math.degrees(math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)))
            pitch = math.degrees(math.asin(max(-1.0, min(1.0, 2 * (w * y - z * x)))))
            print(
                f"t={state.time_ms / 1000:8.2f}s  bus {state.bus_voltage:5.2f} V  logic {state.current:5.2f} A  "
                f"roll {roll:+6.1f}°  pitch {pitch:+6.1f}°  [{active}]"
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="strido-cli", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--port",
        default=os.environ.get("STRIDO_SERIAL_PORT", DEFAULT_PORT),
        help="MCU serial device (env STRIDO_SERIAL_PORT)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("center")
    pulse = sub.add_parser("pulse")
    pulse.add_argument("joint")
    pulse.add_argument("us", type=int)
    sub.add_parser("calibrate")
    sub.add_parser("monitor")
    args = parser.parse_args()
    link = Link(args.port)
    handler = {"center": cmd_center, "pulse": cmd_pulse, "calibrate": cmd_calibrate, "monitor": cmd_monitor}[
        args.command
    ]
    try:
        handler(link, args)
    except KeyboardInterrupt:
        print()
    finally:
        link.close()


if __name__ == "__main__":
    main()
