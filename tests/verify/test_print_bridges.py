"""Hole overhang trick: only real hole steps are cut, and the two layers above them bridge."""

import pytest
import trimesh

from strido_cad.geom import boolean, box, cylinder, to_mesh
from strido_publish.print_bridges import bridge_hole_steps, hole_steps, layers_mm, slot_top_mm


def plate_with_seat():
    """A 5 mm plate with a 16 mm seat 3 mm deep from the bed side, then a 12 mm hole through."""
    plate = to_mesh(box(-20, -20, 0, 20, 20, 5))
    return boolean(plate, cut=[cylinder((0, 0, 0), (0, 0, 1), 8.0, -1, 3), cylinder((0, 0, 0), (0, 0, 1), 6.0, -1, 6)])


def open_areas(mesh: trimesh.Trimesh, z: float) -> list[float]:
    planar, _ = mesh.section(plane_origin=(0, 0, z), plane_normal=(0, 0, 1)).to_2D()
    return sorted(
        round(abs(trimesh.path.polygons.Polygon(ring).area), 0)
        for poly in planar.polygons_full
        for ring in poly.interiors
    )


def test_a_seat_step_is_found_and_cut_into_slot_then_square():
    mesh = plate_with_seat()
    steps = hole_steps(mesh)
    assert [(round(s.narrow_mm), round(s.wide_mm), round(s.z_mm)) for s in steps] == [(12, 16, 3)]
    cut, bridged = bridge_hole_steps(mesh)
    _, layer = layers_mm()
    assert len(bridged) == 1 and bridged[0].from_bed and not hole_steps(cut)
    # the open area: the slot (12 mm wide across the 16 mm seat), then the 12 x 12 square, then the round hole
    slot, square, narrow = (open_areas(cut, 3 + k * layer + layer / 2) for k in range(3))
    assert slot[0] > square[0] > narrow[0]
    assert abs(square[0] - 144) < 3 and abs(narrow[0] - 113) < 3


def test_a_rim_of_the_part_is_no_hole_step():
    # a disc with a wider flange on top: its downward ring is the part's outline, open space below it
    disc = boolean(to_mesh(cylinder((0, 0, 0), (0, 0, 1), 6.0, 0, 3)), add=[cylinder((0, 0, 0), (0, 0, 1), 10.0, 3, 5)])
    with_hole = boolean(disc, cut=[cylinder((0, 0, 0), (0, 0, 1), 2.0, -1, 6)])
    assert hole_steps(with_hole) == []


def test_the_slot_fills_the_first_slicing_layer_above_the_step_wherever_the_step_lies():
    # layers 0.2 mm (first layer 0.2): a step at 4.00 or 4.05 mm is followed by the layer sliced at 4.10 mm
    assert slot_top_mm(4.0, 0.2, 0.2) == pytest.approx(4.2)
    assert slot_top_mm(4.05, 0.2, 0.2) == pytest.approx(4.2)
    assert slot_top_mm(4.12, 0.2, 0.2) == pytest.approx(4.4)
