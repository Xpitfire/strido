"""Fit classification of a measured hole around a screw (hardware/verification/tolerances.yaml)."""

import pytest

from strido_verify import fits


@pytest.mark.parametrize(
    ("hole_mm", "fit", "status"),
    [
        (3.40, "clearance", "ok"),  # ISO 273 medium for M3
        (3.10, "clearance", "warn"),  # prints tight: chase with a drill
        (3.02, "line-to-line", "fail"),  # neither passes nor grips
        (2.50, "thread-forming", "ok"),  # printed 2.35 = 0.78 d
        (2.92, "thread-forming", "warn"),  # printed 2.77 = 0.92 d: weak grip
        (2.99, "thread-forming", "fail"),  # printed 2.84 = 0.95 d: no grip
        (3.00, "line-to-line", "fail"),
        (2.20, "thread-forming", "fail"),  # printed 2.05 = 0.68 d: boss splits
    ],
)
def test_m3_hole_classes(hole_mm, fit, status):
    assert fits.classify(hole_mm, 3.0)[:2] == (fit, status)


def boss(span_mm: float, engaged_mm: float) -> fits.PartFit:
    return fits.PartFit("boss", "boss#1", "strido", 0.0, span_mm, 2.5, "thread-forming", "ok", "", engaged_mm)


def test_screw_with_too_short_engagement_fails_and_short_one_warns():
    short, shorter = boss(3.5, 3.5), boss(2.0, 2.0)
    assert fits.terminate([short], [], 3.0, None, []) == "thread-forming" and short.status == "warn"
    fits.terminate([shorter], [], 3.0, None, [])
    assert shorter.status == "fail"


def test_engagement_counts_only_material_the_screw_cuts():
    # 10 mm through the part, but 8 mm of it is a counterbore/cavity: 2 mm of thread is too short.
    recessed = boss(10.0, 2.0)
    fits.terminate([recessed], [], 3.0, None, [])
    assert recessed.status == "fail"


def test_accepted_deviation_applies_only_to_listed_upstream_parts():
    too_large = fits.classify(2.96, 3.0)
    assert too_large[1] == "fail"
    assert fits.accepted("right_servo_mount", too_large[0], 2.96, 3.0, *too_large[1:])[0] == "warn"
    assert fits.accepted("front_shell_display", too_large[0], 2.96, 3.0, *too_large[1:])[0] == "fail"
    assert fits.accepted("right_servo_mount", too_large[0], 2.99, 3.0, *too_large[1:])[0] == "fail"
    too_small = fits.classify(2.20, 3.0)  # would split the boss: never covered by the oversize acceptance
    assert fits.accepted("right_servo_mount", too_small[0], 2.20, 3.0, *too_small[1:])[0] == "fail"


def test_pilot_on_a_nut_joint_becomes_a_drill_action():
    narrow = fits.PartFit("frame", "frame#1", "upstream STL", 0.0, 4.0, 2.6, "thread-forming", "ok")
    nut = fits.Coaxial("nut", 4.0, 6.4)
    assert fits.terminate([narrow], [nut], 3.0, None, []) == "nut"
    assert (narrow.fit, narrow.status) == ("tight passage", "warn")
