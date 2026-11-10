"""Behavioural tests for the host-side kinematics, gait and MCU protocol."""

import math
import struct

import numpy as np
import pytest

from strido import gait, leg, protocol
from strido.geometry import LEG_NAMES, LEGS


def test_crc_matches_firmware_check_value():
    # CRC-16/CCITT-FALSE check value, same vector as the firmware unit test
    assert protocol.crc16(b"123456789") == 0x29B1


def test_frames_round_trip_and_reject_corruption():
    q = [0.1 * i - 0.5 for i in range(12)]
    frame = protocol.joint_command(7, protocol.MODE_POSITION, q)
    assert frame.count(0) == 1 and frame.endswith(b"\x00")  # COBS: the only zero is the delimiter
    messages = list(protocol.FrameReader().feed(frame))
    assert len(messages) == 1
    message_type, payload = messages[0]
    assert message_type == protocol.JOINT_COMMAND
    seq, mode, *values = struct.unpack("<HB12f", payload)
    assert (seq, mode) == (7, protocol.MODE_POSITION)
    assert np.allclose(values, q, atol=1e-6)
    corrupted = bytearray(frame)
    corrupted[3] ^= 0x5A
    reader = protocol.FrameReader()
    assert list(reader.feed(bytes(corrupted))) == [] and reader.dropped == 1


def test_frame_reader_resynchronises_after_garbage():
    frame = protocol.estop(True)
    messages = list(protocol.FrameReader().feed(b"\x11\x22garbage\x00" + frame + frame))
    assert [m[0] for m in messages] == [protocol.ESTOP, protocol.ESTOP]


def test_state_payload_round_trip():
    state = protocol.State(
        9,
        1234,
        protocol.FLAG_IMU_OK | protocol.FLAG_PWM_OK,
        tuple(range(12)),
        (1.0, 0.0, 0.0, 0.0),
        (0.1, 0.2, 0.3),
        (0.0, 0.0, 9.81),
        7.6,
        1.25,
    )
    decoded = protocol.State.unpack(state.pack())
    assert decoded.status == state.status and decoded.time_ms == 1234
    assert np.allclose(decoded.q, state.q) and math.isclose(decoded.bus_voltage, 7.6, rel_tol=1e-6)


@pytest.mark.parametrize("name", LEG_NAMES)
@pytest.mark.parametrize("height", [0.12, 0.17, 0.21])
def test_inverse_kinematics_inverts_forward_kinematics(name, height):
    stand = gait.TrotGait(gait.GaitConfig(body_height=height)).foot_targets()[name]
    for offset in ([0, 0, 0], [0.03, 0.0, 0.0], [-0.03, 0.01, 0.02]):
        target = stand + np.array(offset)
        q = leg.inverse_kinematics(name, target)
        assert q is not None
        assert np.allclose(leg.foot_position(name, q), target, atol=1e-5)


@pytest.mark.parametrize("name", LEG_NAMES)
def test_knee_linkage_crank_and_calf_are_inverse(name):
    for thigh in np.radians([20.0, 45.0, 70.0]):
        for calf in np.radians([-130.0, -100.0, -70.0]):
            crank = leg.crank_from_calf(name, thigh, calf)
            if crank is None:
                continue
            assert math.isclose(leg.calf_from_crank(name, thigh, crank), calf, abs_tol=1e-6)


@pytest.mark.parametrize(
    "height", [0.10, 0.17, 0.21]
)  # 0.10 m with combined commands drives the knee crank into its limit
def test_gait_respects_joint_and_crank_limits_over_full_cycles(height):
    trot = gait.TrotGait(gait.GaitConfig(body_height=height))
    for command in ((0.3, 0.0, 0.0), (-0.3, 0.0, 0.0), (0.0, 0.15, 0.0), (0.3, 0.15, 1.0), (-0.3, -0.15, -1.0)):
        trot.set_command(*command)
        for _ in range(200):  # 2 s at 100 Hz = 5 gait cycles
            q = trot.step(0.01).reshape(4, 3)
            for name, (hip, thigh, calf) in zip(LEG_NAMES, q):
                limits = LEGS[name]
                assert limits.hip_min - 1e-9 <= hip <= limits.hip_max + 1e-9
                assert limits.thigh_min - 1e-9 <= thigh <= limits.thigh_max + 1e-9
                assert limits.calf_min - 1e-9 <= calf <= limits.calf_max + 1e-9
                crank = leg.crank_from_calf(name, thigh, calf)
                assert crank is not None and limits.crank_min - 1e-6 <= crank <= limits.crank_max + 1e-6


def test_command_is_saturated_to_gait_limits():
    trot = gait.TrotGait()
    trot.set_command(5.0, -5.0, 9.0)
    assert tuple(trot.command) == (trot.config.max_linear[0], -trot.config.max_linear[1], trot.config.max_yaw_rate)


def test_stance_feet_move_backwards_when_walking_forward():
    trot = gait.TrotGait()
    trot.set_command(0.2, 0.0, 0.0)
    trot.time = 0.0
    start = trot.foot_targets()["FL"]  # FL starts its stance phase at phase 0
    trot.time = 0.05
    later = trot.foot_targets()["FL"]
    assert later[0] < start[0] and math.isclose(later[2], start[2])
