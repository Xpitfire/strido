"""Geometry probes for the fit checks: plane cuts around an axis, coaxial items, bearing seats."""

from dataclasses import dataclass

import numpy as np
import trimesh
import yaml
from shapely.geometry import Point, Polygon

from strido.workspace import path
from strido_cad.assembly import Instance

LIMITS = yaml.safe_load(path("hardware/verification/tolerances.yaml").read_text())


@dataclass
class SeatFit:
    bearing: str
    part: str
    od_mm: float
    seat_d_mm: float
    status: str


# --------------------------------------------------------------------------- geometry


def section_state(mesh: trimesh.Trimesh, point: np.ndarray, normal: np.ndarray) -> tuple[str, float]:
    """Cut `mesh` with the plane (point, normal): ('solid'|'hole'|'outside', inscribed diameter mm).

    Cross-sections nest (a boss inside a shell cavity is its own polygon inside the cavity
    ring), so the innermost hole that contains the probe decides."""
    cut = mesh.section(plane_origin=point, plane_normal=normal)
    if cut is None:
        return "outside", 0.0
    planar, to_3d = cut.to_2D(normal=normal, check=False)
    local = np.linalg.inv(to_3d) @ np.append(point, 1.0)
    probe = Point(local[0], local[1])
    holes = []
    for polygon in planar.polygons_full:
        if polygon.contains(probe):
            return "solid", 0.0
        if Polygon(polygon.exterior).contains(probe):
            holes += [probe.distance(ring) for ring in polygon.interiors if Polygon(ring).contains(probe)]
    if holes:
        return "hole", 2.0 * min(holes)
    return "outside", 0.0


def aabb_hits(bounds: np.ndarray, start: np.ndarray, end: np.ndarray, margin: float) -> bool:
    low = np.minimum(start, end) - margin
    high = np.maximum(start, end) + margin
    return bool(np.all(bounds[0] <= high) and np.all(bounds[1] >= low))


@dataclass(frozen=True)
class Coaxial:
    """A part on the screw axis described by its span along the axis (mm from the head)."""

    kind: str  # nut | standoff | bearing
    start: float
    end: float


@dataclass(frozen=True)
class AxialItem:
    """A nut or stand-off (`origin` + `axis` * [0, length]) or a bearing (centred on `origin`)."""

    kind: str
    origin: np.ndarray
    axis: np.ndarray
    length: float


def coaxial_spans(head: np.ndarray, axis: np.ndarray, length: float, items: list[AxialItem]) -> list[Coaxial]:
    """Items whose axis coincides with the screw and that overlap its length."""
    found = []
    for item in items:
        if abs(float(np.dot(item.axis, axis))) < 0.99:
            continue
        offset = item.origin - head
        along = float(np.dot(offset, axis))
        if np.linalg.norm(offset - along * axis) > 0.5:
            continue
        if item.kind == "bearing":
            start, end = along - item.length / 2, along + item.length / 2
        else:
            direction = float(np.sign(np.dot(item.axis, axis)))
            start, end = sorted((along, along + direction * item.length))
        if end >= -0.5 and start <= length + 0.5:
            found.append(Coaxial(item.kind, start, end))
    return found


def bearing_axis(mesh: trimesh.Trimesh, od: float) -> tuple[np.ndarray, np.ndarray]:
    """Centre and axis of a bearing or sleeve: the oriented-box direction whose mid-plane cut is a
    ring of the catalogue outer diameter (a 5x5 sleeve has no distinct thin box axis)."""
    box = mesh.bounding_box_oriented.primitive
    centre = box.transform[:3, 3].copy()
    best: tuple[float, np.ndarray] | None = None
    for column in range(3):
        axis = box.transform[:3, column] / np.linalg.norm(box.transform[:3, column])
        cut = mesh.section(plane_origin=centre, plane_normal=axis)
        if cut is None:
            continue
        planar, _ = cut.to_2D(normal=axis, check=False)
        rings = [p for p in planar.polygons_full if len(p.interiors) == 1]
        if not rings:
            continue
        width, height = np.ptp(np.asarray(rings[0].exterior.coords), axis=0)
        error = abs(width - od) + abs(height - od)
        if best is None or error < best[0]:
            best = (error, axis)
    if best is None:
        raise ValueError("bearing mesh has no ring-shaped cross-section")
    return centre, best[1]


def measure_seats(
    bearings: list[tuple[Instance, trimesh.Trimesh]], printed: list[tuple[Instance, trimesh.Trimesh]]
) -> list[SeatFit]:
    """One row per (bearing, holding part); a bearing that no printed part holds is a failing row."""
    band = LIMITS["bearing_seat"]
    seats = []
    for instance, mesh in bearings:
        spec = LIMITS["bearings"][instance.part.split("/")[1]]
        centre, axis = bearing_axis(mesh, spec["od"])
        held = False
        for part_instance, part_mesh in printed:
            if not aabb_hits(part_mesh.bounds, centre, centre, spec["od"] / 2 + 1.0):
                continue
            state, diameter = section_state(part_mesh, centre, axis)
            if state != "hole" or abs(diameter - spec["od"]) > 1.5:
                continue  # this part does not hold the bearing's outer ring
            held = True
            over = diameter - spec["od"]
            ok = band["min_over_od_mm"] <= over <= band["max_over_od_mm"]
            seats.append(
                SeatFit(
                    instance.id,
                    part_instance.part.split("/")[1],
                    spec["od"],
                    round(diameter, 3),
                    "ok" if ok else "fail",
                )
            )
        if not held:
            seats.append(SeatFit(instance.id, "(no printed seat within 1.5 mm of the OD)", spec["od"], 0.0, "fail"))
    return seats
