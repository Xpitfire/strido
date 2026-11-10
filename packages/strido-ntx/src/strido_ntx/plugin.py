"""`ntx.adapters` entry point: registers the Strido hardware transport with the NT-X registry.

    registry.create("robot", "strido-serial", spec=load_robot("strido"), device="/dev/strido_mcu")

NT-X core still opens hardware through `ntx.deploy.open_robot_port` (Unitree SDK2 only, see
docs/ntx-integration.md); until it dispatches through the registry, this adapter is used
directly by NT-X sessions/scripts that construct it from the registry.
"""

import os
from typing import Any

from ntx.core.contracts import RobotSpec

from .serial_port import StridoSerialPort, open_serial

ADAPTER = "strido-serial"
DEFAULT_DEVICE = "/dev/strido_mcu"


def create_port(spec: RobotSpec, device: str | None = None, state_timeout_s: float = 0.2) -> StridoSerialPort:
    return StridoSerialPort(
        spec, open_serial(device or os.environ.get("STRIDO_SERIAL_PORT", DEFAULT_DEVICE)), state_timeout_s
    )


def register(registry: Any) -> None:
    registry.register(
        "robot",
        ADAPTER,
        create_port,
        transport="usb-cdc (COBS + CRC16)",
        robots=["strido"],
        odometry=False,
        feedback="commanded joint angles, IMU orientation and body rates",
    )
