"""NT-X <-> MCU codec: what a hobby-servo robot can and cannot promise to the NT-X runtime."""

import math

import pytest

from strido import protocol
from strido_ntx import codec
from strido_ntx.fake_mcu import FakeMcu

STAND = [0.0, 0.78, -1.5] * 4


def test_position_target_round_trips_through_the_wire_format():
    mcu = FakeMcu()
    mcu.write(codec.encode_joint_command(3, STAND))
    assert mcu.q == pytest.approx(STAND, abs=1e-6)
    ((message_type, payload),) = protocol.FrameReader().feed(mcu.read(4096))
    state = codec.decode_state(payload)
    assert message_type == protocol.STATE and state.q == pytest.approx(STAND, abs=1e-6) and state.imu_ok
    assert state.command_seq == 3


@pytest.mark.parametrize(
    ("q", "dq", "kp", "reason"),
    [
        (STAND[:11], None, None, "expected 12"),
        ([math.nan, *STAND[1:]], None, None, "non-finite"),
        (STAND, [0.1] * 12, None, "dq"),
        (STAND, None, [20.0] * 11 + [0.0], "kp <= 0"),
    ],
)
def test_commands_a_position_servo_cannot_execute_are_rejected(q, dq, kp, reason):
    with pytest.raises(codec.CommandRejectedError, match=reason):
        codec.encode_joint_command(1, q, dq, kp)


def test_pd_command_with_positive_gains_runs_as_a_position_target():
    # NT-X pose runtimes send kp/kd and gravity feed-forward; the servo's own loop replaces both.
    mcu = FakeMcu()
    mcu.write(codec.encode_joint_command(1, STAND, [0.0] * 12, [20.0] * 12))
    assert mcu.q == pytest.approx(STAND, abs=1e-6)


def test_stop_latches_and_blocks_motion_until_release():
    mcu = FakeMcu()
    mcu.write(codec.encode_stop())
    mcu.write(codec.encode_joint_command(2, STAND))
    assert mcu.estop and mcu.q == [0.0] * 12
    mcu.write(codec.encode_release())
    mcu.write(codec.encode_joint_command(3, STAND))
    assert not mcu.estop and mcu.q == pytest.approx(STAND, abs=1e-6)


def test_state_flags_are_decoded():
    mcu = FakeMcu()
    mcu.write(codec.encode_stop())
    ((_, payload),) = protocol.FrameReader().feed(mcu.read(4096))
    state = codec.decode_state(payload)
    assert state.stopped and {"estop", "imu_ok", "power_ok"} <= state.flags


def test_truncated_state_payload_is_rejected():
    with pytest.raises(ValueError, match="bytes"):
        codec.decode_state(b"\x00" * 10)
