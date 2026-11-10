"""Simple, dimensionally correct meshes for catalogue fasteners (for renders and checks).

Canonical frame: bearing face (under the head / nut face) at z=0, the fastener
extends along +z into the joint. Threads are modelled as their nominal cylinder.
"""

from functools import cache
from pathlib import Path

import numpy as np
import trimesh
import yaml

from .paths import CAD_CACHE, FASTENER_CATALOGUE

CATALOGUE = yaml.safe_load(FASTENER_CATALOGUE.read_text())
OUT = CAD_CACHE / "fasteners"


def _cylinder(radius, z0, z1, sections=24):
    mesh = trimesh.creation.cylinder(radius=radius, height=z1 - z0, sections=sections)
    mesh.apply_translation((0, 0, (z0 + z1) / 2))
    return mesh


def _hex(across_flats, z0, z1):
    radius = across_flats / np.sqrt(3.0)
    mesh = trimesh.creation.cylinder(radius=radius, height=z1 - z0, sections=6)
    mesh.apply_translation((0, 0, (z0 + z1) / 2))
    return mesh


def spec(key: str) -> dict:
    item = dict(CATALOGUE["items"][key])
    item.update(CATALOGUE["thread"][item["thread"]])
    return item


@cache
def mesh_path(key: str) -> Path:
    """Mesh file of a catalogue fastener; screws: head on z<0, shank 0..length along +z."""
    item = spec(key)
    if item["kind"] == "screw":
        head_height = item["k"] if item["standard"] == "iso4762" else 0.55 * item["k"] + 0.0
        head = _cylinder(item["dk"] / 2, -head_height, 0.0)
        shank = _cylinder(item["d"] / 2 * 0.97, 0.0, item["length"])
        mesh = trimesh.boolean.union([head, shank], engine="manifold")
    elif item["kind"] == "nut":
        height = item["h"] if item["standard"] == "din985" else item["m"]
        mesh = trimesh.boolean.difference(
            [_hex(item["s"], 0.0, height), _cylinder(item["d"] / 2, -1, height + 1)], engine="manifold"
        )
    elif item["kind"] == "washer":
        mesh = trimesh.boolean.difference(
            [_cylinder(item["washer_od"] / 2, 0, item["washer_t"]), _cylinder(item["d"] / 2 + 0.1, -1, 2)],
            engine="manifold",
        )
    elif item["kind"] == "standoff":
        mesh = trimesh.boolean.difference(
            [_hex(item["across_flats"], 0.0, item["length"]), _cylinder(item["d"] / 2, -1, item["length"] + 1)],
            engine="manifold",
        )
    else:
        raise ValueError(item["kind"])
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{key}.stl"
    mesh.export(path)
    return path


def placement(head, axis) -> np.ndarray:
    """4x4 placing the canonical fastener with its bearing face at `head` pointing along `axis`."""
    axis = np.asarray(axis, dtype=float)
    axis /= np.linalg.norm(axis)
    matrix = trimesh.geometry.align_vectors([0.0, 0.0, 1.0], axis)
    matrix[:3, 3] = head
    return matrix
