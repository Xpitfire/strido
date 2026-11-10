"""Small geometry helpers shared by the Strido part builders (millimetres)."""

import cadquery as cq
import manifold3d
import numpy as np
import trimesh


def box(x0, y0, z0, x1, y1, z1) -> cq.Workplane:
    """Axis-aligned box from two corners."""
    lo = np.minimum((x0, y0, z0), (x1, y1, z1))
    hi = np.maximum((x0, y0, z0), (x1, y1, z1))
    size = hi - lo
    return cq.Workplane("XY").box(*size, centered=False).translate(tuple(lo))


def cylinder(centre, axis, radius, z0, z1) -> cq.Workplane:
    """Cylinder whose axis passes through `centre` along unit `axis`, spanning z0..z1 along it."""
    axis = np.asarray(axis, dtype=float)
    axis /= np.linalg.norm(axis)
    start = np.asarray(centre, dtype=float) + axis * z0
    plane = cq.Plane(origin=tuple(start), xDir=_perpendicular(axis), normal=tuple(axis))
    return cq.Workplane(plane).circle(radius).extrude(z1 - z0)


def _perpendicular(axis) -> tuple:
    helper = np.array([0.0, 0.0, 1.0]) if abs(axis[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    x_dir = np.cross(helper, axis)
    return tuple(x_dir / np.linalg.norm(x_dir))


def to_mesh(shape: cq.Workplane, tolerance=0.05) -> trimesh.Trimesh:
    solid = shape.val() if hasattr(shape, "val") else shape
    if hasattr(shape, "vals") and len(shape.vals()) > 1:
        solid = cq.Compound.makeCompound(shape.vals())
    vertices, triangles = solid.tessellate(tolerance, 0.2)
    mesh = trimesh.Trimesh(np.array([[v.x, v.y, v.z] for v in vertices]), np.array(triangles), process=True)
    mesh.merge_vertices()
    return mesh


def to_manifold(mesh: trimesh.Trimesh) -> manifold3d.Manifold:
    solid = manifold3d.Manifold(
        manifold3d.Mesh(
            vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
            tri_verts=np.asarray(mesh.faces, dtype=np.uint32),
        )
    )
    assert solid.status() == manifold3d.Error.NoError, solid.status()
    return solid


def from_manifold(solid: manifold3d.Manifold) -> trimesh.Trimesh:
    """Manifold output is already indexed and closed; re-processing can merge vertices across thin walls."""
    mesh = solid.to_mesh()
    return trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts), process=False)


def boolean(base: trimesh.Trimesh, add=(), cut=()) -> trimesh.Trimesh:
    """Exact mesh booleans: (base U add...) - cut... ; inputs are trimesh or CadQuery shapes."""
    solid = to_manifold(base)
    for item in add:
        solid = solid + to_manifold(item if isinstance(item, trimesh.Trimesh) else to_mesh(item))
    for item in cut:
        solid = solid - to_manifold(item if isinstance(item, trimesh.Trimesh) else to_mesh(item))
    result = from_manifold(solid)
    assert result.is_watertight, "boolean result is not watertight"
    return result


def rotation(columns) -> np.ndarray:
    """4x4 rotation whose columns are the images of the local x, y, z axes."""
    matrix = np.eye(4)
    matrix[:3, :3] = np.array(columns, dtype=float).T
    return matrix


def translation(vector) -> np.ndarray:
    matrix = np.eye(4)
    matrix[:3, 3] = vector
    return matrix


def lay_flat(mesh: trimesh.Trimesh, down: np.ndarray) -> np.ndarray:
    """Transform that rotates `down` (world direction) onto -Z and drops the part on z=0, centred in XY."""
    down = np.asarray(down, dtype=float)
    down /= np.linalg.norm(down)
    rotate = trimesh.geometry.align_vectors(down, [0.0, 0.0, -1.0])
    placed = mesh.copy()
    placed.apply_transform(rotate)
    lo, hi = placed.bounds
    shift = translation([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])
    return shift @ rotate
