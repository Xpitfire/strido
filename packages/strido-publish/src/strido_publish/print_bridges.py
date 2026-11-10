"""Hole overhang trick for the print kit: bridge every hole step instead of supporting it.

A step from a wide hole below (a bearing seat, a counterbore opening on the bed side) to a narrower
hole above leaves a ring that hangs in the air: the slicer either supports it (and the support has to
be dug out of the bore) or prints loose loops. Two layers of material removed at the step make it
bridgeable (the trick as described by builders of FDM parts):

* layer 1 above the step: a slot as wide as the narrow hole, across the whole wide hole; the material
  either side of it is a straight bridge between the wide hole's walls;
* layer 2: a square as wide as the narrow hole; the material either side bridges across the slot,
  resting on layer 1;
* layer 3 on: the narrow hole as designed, resting on layer 2.

The cuts stay inside the wide hole's outline, so the seat diameter and the narrow hole are unchanged;
the step loses at most two layers where the slot runs. Applied to the kit STLs only (not to the CAD),
on the print orientation.
"""

import configparser
from dataclasses import dataclass

import numpy as np
import trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union

from strido.workspace import path
from strido_cad.geom import boolean, box, cylinder

PROFILE = path("hardware/print/prusaslicer.ini")
ROUND = 0.85  # 4πA/P² of a ring that counts as a round hole (a polygonised circle is ~0.99, a square 0.79)
MIN_HEIGHT_MM = 0.3  # a step at or below this lies on the bed
MIN_RING_MM = 0.4  # radial width of a step worth bridging: one extrusion line; narrower steps print as they are


@dataclass(frozen=True)
class HoleStep:
    centre: tuple[float, float]
    z_mm: float
    narrow_mm: float  # diameter of the hole above the step
    wide_mm: float  # diameter of the hole below
    from_bed: bool  # the wide hole opens onto the bed: nothing below it for a slicer to support


def layers_mm() -> tuple[float, float]:
    """(first layer height, layer height) of the kit profile."""
    parser = configparser.ConfigParser()
    parser.read_string("[profile]\n" + PROFILE.read_text())  # PrusaSlicer ini has no section header
    return float(parser["profile"]["first_layer_height"]), float(parser["profile"]["layer_height"])


def slot_top_mm(step_z: float, first: float, layer: float) -> float:
    """Top of the first slicing layer whose middle (where the slicer cuts it) lies above the step."""
    top = first
    while top - (layer if top > first else first) / 2 <= step_z:
        top += layer
    return top


def roundness(ring) -> float:
    polygon = Polygon(ring)
    return 4 * np.pi * polygon.area / polygon.length**2


def has_hole(mesh: trimesh.Trimesh, z: float, centre, area: float) -> bool:
    """True when the part's cross-section at height z has a hole of about this area around this centre
    (a ring of material around it, not open space beside the part)."""
    section = mesh.section(plane_origin=(0.0, 0.0, z), plane_normal=(0, 0, 1))
    if section is None:
        return False
    planar, to_3d = section.to_2D()
    for polygon in planar.polygons_full:
        for ring in polygon.interiors:
            hole = Polygon(ring)
            middle = (to_3d @ np.array([hole.centroid.x, hole.centroid.y, 0.0, 1.0]))[:2]
            if np.hypot(*(middle - centre)) < 0.5 and abs(hole.area - area) < 0.15 * area:
                return True
    return False


def hole_steps(mesh: trimesh.Trimesh) -> list[HoleStep]:
    """Downward-facing rings above the bed whose inside is a round narrow hole and whose outline is a
    round wide hole around it (concentric within 0.5 mm), with material around both holes."""
    down = (mesh.face_normals[:, 2] < -0.999) & (mesh.triangles_center[:, 2] > MIN_HEIGHT_MM)
    steps = []
    for z in np.unique(np.round(mesh.triangles_center[down, 2], 2)):
        faces = down & (np.abs(mesh.triangles_center[:, 2] - z) < 0.01)
        region = (
            unary_union([Polygon(triangle[:, :2]) for triangle in mesh.triangles[faces]]).buffer(0.01).buffer(-0.01)
        )
        for polygon in getattr(region, "geoms", [region]):
            if (
                len(polygon.interiors) != 1
                or roundness(polygon.exterior) < ROUND
                or roundness(polygon.interiors[0]) < ROUND
            ):
                continue
            outer, inner = Polygon(polygon.exterior), Polygon(polygon.interiors[0])
            centre = np.array([outer.centroid.x, outer.centroid.y])
            if outer.centroid.distance(inner.centroid) > 0.5:
                continue
            if np.sqrt(outer.area / np.pi) - np.sqrt(inner.area / np.pi) < MIN_RING_MM:
                continue
            if not (has_hole(mesh, z - 0.1, centre, outer.area) and has_hole(mesh, z + 0.1, centre, inner.area)):
                continue  # a rim of the part's outline, not a hole step
            steps.append(
                HoleStep(
                    (outer.centroid.x, outer.centroid.y),
                    float(z),
                    2 * float(np.sqrt(inner.area / np.pi)),
                    2 * float(np.sqrt(outer.area / np.pi)),
                    has_hole(mesh, MIN_HEIGHT_MM / 2, centre, outer.area),
                )
            )
    return steps


def bridge_hole_steps(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, list[HoleStep]]:
    """The mesh (in print orientation) with every hole step cut for bridging, and the steps. The slot
    fills the first slicing layer above the step, the square the next one."""
    steps = hole_steps(mesh)
    if not steps:
        return mesh, []
    first, layer = layers_mm()
    cuts = []
    for step in steps:
        x, y = step.centre
        half, wide = step.narrow_mm / 2, step.wide_mm / 2
        top = slot_top_mm(step.z_mm, first, layer)
        disk = cylinder(
            (x, y, step.z_mm), (0, 0, 1), wide, -0.01, top + layer - step.z_mm
        )  # never outside the wide hole
        slot = box(x - wide, y - half, step.z_mm - 0.01, x + wide, y + half, top)
        square = box(x - half, y - half, top - 0.01, x + half, y + half, top + layer)
        cuts += [slot.intersect(disk), square.intersect(disk)]
    return boolean(mesh, cut=cuts), steps
