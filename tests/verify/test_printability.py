"""Printability gate helpers: slicer time parsing and the thin-wall measure (no slicer needed)."""

import numpy as np
import trimesh

from strido_verify import printability


def test_slicer_durations_parse_to_seconds():
    assert printability.duration_s("1d 2h 13m 56s") == 86400 + 2 * 3600 + 13 * 60 + 56
    assert printability.duration_s("45m 3s") == 45 * 60 + 3


def thin_area(points: np.ndarray) -> float:
    return printability.thin_wall_area(points, np.ones(len(points), dtype=bool), area_per_sample=0.0625)


def test_short_cusp_lines_are_ignored_but_patches_and_long_fins_count():
    # Sampled at 0.25 mm: a 0.25 mm wide, 2 mm long cusp where a hole grazes a face; a 3 x 3 mm thin
    # patch; a 0.25 mm wide, 10 mm long knife-edge fin.
    grid = np.arange(0.0, 3.0, 0.25)
    cusp = np.array([(x, y, 0.0) for x in np.arange(0.0, 2.0, 0.25) for y in (0.0, 0.25)])
    patch = np.array([(20.0 + x, y, 0.0) for x in grid for y in grid])
    fin = np.array([(40.0 + x, y, 0.0) for x in np.arange(0.0, 10.0, 0.25) for y in (0.0, 0.25)])
    assert thin_area(cusp) == 0.0
    assert thin_area(np.vstack([cusp, patch])) == len(patch) * 0.0625
    assert thin_area(fin) == len(fin) * 0.0625


def test_any_unexpected_slicer_message_or_missing_gcode_fails_the_slice():
    gcode = "; total filament used [g] = 12.30\n"
    stability = [
        "print warning: Detected print stability issues:",
        "part.stl",
        "Low bed adhesion",
        "Consider enabling supports.",
    ]
    assert printability.slice_failures(0, stability, gcode) == []  # judged separately by stability_issues
    assert printability.stability_issues(stability) == {"Low bed adhesion"}
    conflict = ["[error]   gcode path conflicts found between a.stl and b.stl"]
    assert printability.slice_failures(0, conflict, gcode) == [f"slicer: {conflict[0]}"]
    assert printability.slice_failures(0, [], "") == ["no complete G-code"]
    assert printability.slice_failures(-11, [], gcode) == ["slicer exit code -11"]


def test_a_wall_thinner_than_one_extrusion_line_fails_the_scan():
    thin_fin = trimesh.creation.box(extents=(0.3, 20.0, 10.0))  # 0.3 mm upright fin: lateral wall
    scan = printability.thickness_scan(thin_fin)
    assert scan["too_thin_lateral_mm2"] > printability.LIMITS["thin_area_mm2"]["fail_above"]
    solid = printability.thickness_scan(trimesh.creation.box(extents=(5.0, 20.0, 10.0)))
    assert solid["thin_lateral_mm2"] == 0.0
