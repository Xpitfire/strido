"""Regression guards for the v0.2 fit defects, measured on the real CAD assembly (`make test-cad`)."""

import pytest

from strido_verify import fits

pytestmark = pytest.mark.cad


@pytest.fixture(scope="module")
def screws() -> list[fits.ScrewFit]:
    measured, seats = fits.run()
    assert all(seat.status != "fail" for seat in seats)
    return measured


def test_no_screw_fit_fails(screws: list[fits.ScrewFit]) -> None:
    failed = [screw.instance for screw in screws if screw.status == "fail"]
    assert failed == []


def test_every_hip_pivot_screw_threads_into_a_servo_mount(screws: list[fits.ScrewFit]) -> None:
    # Defect: the front legs use the opposite mount face, which had no pilot (now *_fl / *_fr print variants).
    pivots = [screw for screw in screws if screw.joint == "hip_pivot"]
    assert len(pivots) == 4
    threaded_into = sorted(part.part for screw in pivots for part in screw.parts if part.fit == "thread-forming")
    assert threaded_into == ["left_servo_mount", "left_servo_mount_fl", "right_servo_mount", "right_servo_mount_fr"]
    assert all(screw.termination == "thread-forming" for screw in pivots)


def test_lidar_pedestal_screws_engage_the_pedestal(screws: list[fits.ScrewFit]) -> None:
    # Defect: the pedestal pilots were too shallow, so the M3x12 screws bottomed out before clamping the shell.
    pedestal = [screw for screw in screws if screw.joint.startswith("pedestal -> top shell")]
    assert len(pedestal) == 4
    for screw in pedestal:
        engaged = [part for part in screw.parts if part.part == "lidar_pedestal"]
        assert [(part.fit, part.status) for part in engaged] == [("thread-forming", "ok")]
