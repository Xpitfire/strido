"""Strength check: section mechanics match the textbook formulas, and only ADR-listed checks are excused."""

import numpy as np
import pytest
from shapely.geometry import Polygon, box

from strido_verify.strength import CONFIG, grade
from strido_verify.strength_sections import directional_moments, section_properties, weakest_section


def test_hollow_rectangle_matches_the_textbook_section_modulus():
    outer = box(-5, -4, 5, 4)  # 10 mm wide, 8 mm high
    hollow = Polygon(outer.exterior.coords, [box(-3, -2, 3, 2).exterior.coords])
    area, centroid, _ = section_properties(hollow)
    inertia, modulus = directional_moments(outer, hollow, np.array([0.0, 1.0]))  # fibres along y: bending about x
    expected_inertia = 10 * 8**3 / 12 - 6 * 4**3 / 12
    assert area == pytest.approx(80 - 24)
    assert centroid == pytest.approx([0, 0])
    assert inertia == pytest.approx(expected_inertia)
    assert modulus == pytest.approx(expected_inertia / 4)


def test_offset_section_uses_its_own_centroid():
    shifted = box(20, 10, 30, 18)
    inertia, _ = directional_moments(shifted, shifted, np.array([0.0, 1.0]))
    assert inertia == pytest.approx(10 * 8**3 / 12)


def test_only_an_adr_listed_check_turns_a_failure_into_a_warning_and_only_down_to_its_bound(monkeypatch):
    accepted = {"long_link_buckling": {"adr": "ADR-999", "min_safety": 0.3, "action": "inspect the links"}}
    monkeypatch.setitem(CONFIG, "accepted", accepted)
    assert grade(0.34, "long_link_buckling")[0] == "warn"
    assert "ADR-999" in grade(0.34, "long_link_buckling")[1]
    assert grade(0.29, "long_link_buckling") == ("fail", "")
    assert grade(1.05, "femur_bending") == ("fail", "")
    assert grade(1.8, "femur_bending") == ("warn", "")
    assert grade(2.5, "long_link_buckling") == ("ok", "")


def test_link_bending_plane_follows_the_pin_bores_not_the_thinnest_dimension():
    # The stiff long link is a 10 x 10 mm bar: equal stiffness both ways, so the walls-only sections must
    # agree. The femur's thin dimension is along its pins: stiffer in the leg plane than across it.
    long_link, femur = weakest_section("stiff_long_link", 1.2), weakest_section("femur", 1.2)
    assert long_link.i_in_mm4 == pytest.approx(long_link.i_out_mm4, rel=0.02)
    assert long_link.i_in_mm4 == pytest.approx((10**4 - 7.6**4) / 12, rel=0.02)  # hollow square, 1.2 mm walls
    assert femur.i_in_mm4 > femur.i_out_mm4
