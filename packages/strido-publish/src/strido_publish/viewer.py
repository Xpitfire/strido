"""Web 3D viewer assets: the standing robot as one GLB plus per-node assembly metadata.

    make viewer

Outputs (served by the docs site at /viewer/):
  docs/viewer/strido.glb      every printed part, purchased part and fastener of the verified CAD,
                               standing at 170 mm, metres, glTF Y-up; repeated meshes are instanced
  docs/viewer/assembly.json    node -> part id, title, kind, manual step, explode vector; step titles
  docs/viewer/face.png         the LCD face texture (also used by the renders)

Meshes are decimated per part kind so the file stays small enough for a web page; the CAD
checks never use these meshes.
"""

import hashlib
import json
import re
from collections import Counter

import numpy as np
import trimesh

from strido.workspace import path
from strido_cad import assembly, catalog
from strido_verify.poses import standing

from . import face, manual_select, manual_steps, part_titles, scene

OUT = path("docs/viewer")
GLB = OUT / "strido.glb"
META = OUT / "assembly.json"
FACE = OUT / "face.png"
FACES_PER_KIND = {"printed": 2500, "purchased": 1200, "fastener": 160, "cable": 600}
SHELLS = {"top_shell_sensor", "front_shell_display", "back_shell_button", "bottom_shell"}
EXPLODE_BASE_M, EXPLODE_GAIN = 0.05, 0.9
STAND_HEIGHT_M = 0.17
# glTF is Y-up: robot (x forward, y left, z up) -> glTF (x, z, -y)
Z_UP_TO_Y_UP = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], dtype=float)
# characters that are not safe in a glTF node name
UNSAFE = re.compile(r"[^A-Za-z0-9_.-]")


def node_name(instance_id: str) -> str:
    return UNSAFE.sub("_", instance_id)


def material(instance) -> trimesh.visual.material.PBRMaterial:
    red, green, blue = scene.colour(instance)
    metallic = 0.85 if scene.is_metal(instance) else 0.0
    return trimesh.visual.material.PBRMaterial(
        baseColorFactor=[red, green, blue, 1.0], metallicFactor=metallic, roughnessFactor=0.35 if metallic else 0.6
    )


def web_mesh(instance) -> trimesh.Trimesh:
    mesh = assembly.load_mesh(instance.mesh).copy()
    target = FACES_PER_KIND.get(instance.kind, 1200)
    if len(mesh.faces) > target:
        mesh = mesh.simplify_quadric_decimation(face_count=target)
    mesh.visual = trimesh.visual.TextureVisuals(material=material(instance))
    return mesh


def face_quad(to_world: np.ndarray) -> trimesh.Trimesh:
    """LCD face texture on a quad just in front of the panel glass; faces the robot's front (-y STEP)."""
    corners = np.array(face.corners_mm())
    quad = trimesh.Trimesh(
        vertices=trimesh.transform_points(corners, to_world), faces=[[0, 1, 2], [0, 2, 3]], process=False
    )
    uv = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=float)
    image = face.face_image()
    texture = trimesh.visual.material.PBRMaterial(
        baseColorTexture=image,
        emissiveTexture=image,
        emissiveFactor=[1.0, 1.0, 1.0],
        metallicFactor=0.0,
        roughnessFactor=0.3,
    )
    quad.visual = trimesh.visual.TextureVisuals(uv=uv, material=texture)
    return quad


def main() -> None:
    instances = [i for i in catalog.full_assembly() if i.kind != "reference"]
    groups = manual_steps.assign(instances)
    step_of = {i.id: index for index, group in enumerate(groups, start=1) for i in group}
    posed = assembly.posed(instances, standing(STAND_HEIGHT_M))
    to_base_m = np.diag([1e-3, 1e-3, 1e-3, 1.0]) @ assembly.step_to_base()
    lift = np.eye(4)
    lift[2, 3] = STAND_HEIGHT_M + 0.012  # hip axes above the ground: stand height + foot radius
    to_world = Z_UP_TO_Y_UP @ lift @ to_base_m
    world_scene = trimesh.Scene()
    geometry_keys: dict[str, str] = {}
    centres = {}
    for instance in posed:
        key = hashlib.sha1(f"{instance.mesh}|{scene.colour(instance)}".encode()).hexdigest()[:12]
        if key not in geometry_keys:
            world_scene.geometry[key] = web_mesh(
                instance
            )  # no node of its own: add_geometry would also place it at the origin
            geometry_keys[key] = key
        transform = to_world @ instance.matrix
        world_scene.graph.update(
            frame_to=node_name(instance.id), frame_from=world_scene.graph.base_frame, matrix=transform, geometry=key
        )
        centres[instance.id] = trimesh.transform_points(
            [assembly.load_mesh(instance.mesh).bounds.mean(axis=0)], transform
        )[0]
    world_scene.add_geometry(face_quad(to_world), geom_name="lcd_face", node_name="lcd_face")
    robot_centre = np.mean(list(centres.values()), axis=0)
    nodes = {}
    for instance in posed:
        offset = centres[instance.id] - robot_centre
        distance = float(np.linalg.norm(offset))
        direction = offset / distance if distance > 1e-6 else np.array([0.0, 1.0, 0.0])
        name = manual_select.kind(instance)
        nodes[node_name(instance.id)] = {
            "part": name,
            "title": part_titles.title(name).replace(" (printed)", ""),
            "kind": instance.kind,
            "step": step_of.get(instance.id, 0),
            "shell": name in SHELLS,
            "explode": [round(float(v), 4) for v in direction * (EXPLODE_BASE_M + EXPLODE_GAIN * distance)],
        }
    nodes["lcd_face"] = {
        "part": "waveshare_lcd_2inch",
        "title": "LCD face (firmware default expression)",
        "kind": "purchased",
        "step": step_of.get(next(i.id for i in posed if manual_select.kind(i) == "waveshare_lcd_2inch"), 0),
        "shell": False,
        "explode": nodes[node_name(next(i.id for i in posed if manual_select.kind(i) == "waveshare_lcd_2inch"))][
            "explode"
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    face.face_image().save(FACE)
    GLB.write_bytes(world_scene.export(file_type="glb"))
    meta = {
        "generated_by": "strido_publish.viewer",
        "units": "m",
        "up": "y",
        "stand_height_m": STAND_HEIGHT_M,
        "steps": [{"index": index, "title": step.title} for index, step in enumerate(manual_steps.STEPS, start=1)],
        "counts": dict(Counter(manual_select.kind(i) for i in posed)),
        "nodes": nodes,
    }
    META.write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n")
    print(
        f"wrote {GLB.name} ({GLB.stat().st_size / 1e6:.1f} MB, {len(posed)} nodes, {len(geometry_keys)} meshes) and {META.name}"
    )


if __name__ == "__main__":
    main()
