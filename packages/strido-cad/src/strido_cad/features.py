"""Extract cylindrical features (holes, bosses, shafts) from B-rep solids.

Used to (a) derive every fastener joint from coaxial holes across mating parts and
(b) measure linkage pivots so the knee transmission can be modelled exactly.
"""

from dataclasses import dataclass

import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.BRepTools import BRepTools
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape


@dataclass
class Cylinder:
    """A cylindrical surface patch merged per (axis line, radius)."""

    radius_mm: float
    axis_point_mm: np.ndarray  # point on the axis closest to the origin
    axis_direction: np.ndarray  # unit vector, canonical sign (first non-zero component positive)
    span_mm: tuple[float, float]  # extent along the axis, measured from axis_point_mm
    is_hole: bool  # True when the material is outside the cylinder (concave face)
    angle_deg: float  # angular coverage of the merged patches (360 = full bore)

    def contains_line(self, point: np.ndarray, direction: np.ndarray, tolerance_mm: float) -> bool:
        if abs(abs(float(np.dot(direction, self.axis_direction))) - 1.0) > 1e-3:
            return False
        offset = point - self.axis_point_mm
        lateral = offset - np.dot(offset, self.axis_direction) * self.axis_direction
        return float(np.linalg.norm(lateral)) < tolerance_mm


def _canonical_direction(direction: np.ndarray) -> np.ndarray:
    direction = direction / np.linalg.norm(direction)
    for component in direction:
        if abs(component) > 1e-6:
            return direction if component > 0 else -direction
    raise AssertionError("zero direction")


def _closest_axis_point(point: np.ndarray, direction: np.ndarray) -> np.ndarray:
    return point - np.dot(point, direction) * direction


def cylinders(shape: TopoDS_Shape, radius_max_mm: float = 30.0) -> list[Cylinder]:
    """Return merged cylindrical features of a solid in its placed coordinates."""
    patches = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        explorer.Next()
        surface = BRepAdaptor_Surface(face, True)
        if surface.GetType() != GeomAbs_Cylinder:
            continue
        cylinder = surface.Cylinder()
        radius = cylinder.Radius()
        if radius > radius_max_mm:
            continue
        axis = cylinder.Axis()
        location = np.array([axis.Location().X(), axis.Location().Y(), axis.Location().Z()])
        raw_direction = np.array([axis.Direction().X(), axis.Direction().Y(), axis.Direction().Z()])
        direction = _canonical_direction(raw_direction)
        u_min, u_max, v_min, v_max = BRepTools.UVBounds_s(face)
        # v runs along the raw axis direction from the axis location.
        sign = 1.0 if np.dot(raw_direction, direction) > 0 else -1.0
        base = _closest_axis_point(location, direction)
        shift = float(np.dot(location - base, direction))
        span = sorted((shift + sign * v_min, shift + sign * v_max))
        # The natural normal of a direct cylinder points away from its axis; an
        # indirect frame or a reversed face flips it. Holes face the axis.
        natural_outward = cylinder.Position().Direct()
        reversed_face = face.Orientation() == TopAbs_REVERSED
        is_hole = natural_outward == reversed_face
        patches.append((radius, base, direction, span, is_hole, float(np.degrees(u_max - u_min))))

    merged = []
    for radius, base, direction, span, is_hole, angle in patches:
        for existing in merged:
            same_axis = (
                abs(existing.radius_mm - radius) < 1e-3
                and existing.is_hole == is_hole
                and abs(float(np.dot(existing.axis_direction, direction))) > 1 - 1e-6
                and np.linalg.norm(existing.axis_point_mm - base) < 1e-3
            )
            overlapping = span[0] <= existing.span_mm[1] + 1e-3 and span[1] >= existing.span_mm[0] - 1e-3
            if same_axis and overlapping:
                existing.span_mm = (min(existing.span_mm[0], span[0]), max(existing.span_mm[1], span[1]))
                existing.angle_deg = min(360.0, existing.angle_deg + angle)
                break
        else:
            merged.append(Cylinder(radius, base, direction, (span[0], span[1]), is_hole, angle))
    return merged


def solid_volume_mm3(shape: TopoDS_Shape) -> float:
    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, properties)
    return properties.Mass()
