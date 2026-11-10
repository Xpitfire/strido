"""Turn assembly instances into Blender render jobs (see blender/render_job.py).

Colours follow the Strido look (lime shells, graphite frame, blue servos);
`style="ikea"` turns everything white with ink outlines and highlights the parts
of the current assembly step.
"""

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import trimesh

from strido.workspace import path, repo_root

REPO = repo_root()
TMP = path("build/render/tmp")
RENDER_JOB_SCRIPT = Path(__file__).resolve().parent / "blender/render_job.py"
MACOS_BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"


def blender_executable() -> str:
    """Blender binary: STRIDO_BLENDER, else `blender` on PATH, else the macOS app bundle."""
    configured = os.environ.get("STRIDO_BLENDER")
    if configured:
        return configured
    return shutil.which("blender") or MACOS_BLENDER


LIME = (0.78, 0.88, 0.12)
GRAPHITE = (0.16, 0.16, 0.17)
COLOURS = {
    "top_shell_sensor": LIME,
    "front_shell_display": LIME,
    "back_shell_button": LIME,
    "bottom_shell": LIME,
    "left_shoulder": LIME,
    "right_shoulder": LIME,
    "lidar_pedestal": GRAPHITE,
    "camera_mount_base": GRAPHITE,
    "servo_spt5435lv": (0.10, 0.18, 0.62),
    "raspberry_pi_5": (0.12, 0.42, 0.22),
    "adafruit_pca9685": (0.10, 0.20, 0.55),
    "seeed_xiao_esp32s3": (0.25, 0.25, 0.28),
    "rplidar_c1": (0.06, 0.06, 0.07),
    "rpi_camera_module_3_wide": (0.10, 0.40, 0.20),
    "waveshare_lcd_2inch": (0.05, 0.05, 0.08),
    "lipo_2s_5000_gensace": (0.75, 0.12, 0.10),
    "wago_221_415": (0.95, 0.55, 0.12),
    "adafruit_lsm6dsox": (0.10, 0.20, 0.55),
    "adafruit_ina260": (0.10, 0.20, 0.55),
    "pololu_d36v50f5": (0.10, 0.45, 0.20),
    "pololu_power_switch_hp": (0.10, 0.45, 0.20),
    "rplidar_usb_adapter": (0.10, 0.20, 0.55),
    "hobbywing_ubec_10a": (0.15, 0.15, 0.20),
    "fuse_holder_ato": (0.10, 0.10, 0.10),
    "pushbutton_12mm": (0.75, 0.75, 0.78),
    "xt60h_female": (0.90, 0.75, 0.10),
    "cable_tie_mount": (0.08, 0.08, 0.09),
}
# Cable conductors by insulation colour (meta "colour" of strido_cad.wiring_geometry instances)
CABLE_COLOURS = {
    "red": (0.78, 0.07, 0.06),
    "black": (0.05, 0.05, 0.05),
    "brown": (0.36, 0.20, 0.10),
    "orange": (0.95, 0.45, 0.05),
    "yellow": (0.95, 0.80, 0.10),
    "blue": (0.10, 0.30, 0.80),
    "green": (0.10, 0.55, 0.20),
    "white": (0.90, 0.90, 0.88),
    "grey": (0.45, 0.45, 0.47),
    "ffc": (0.85, 0.72, 0.45),
    "sleeve": (0.10, 0.10, 0.11),
    "tie": (0.88, 0.86, 0.80),
}
METAL = ("bearing", "horn", "iso4762", "iso7380", "iso4032", "din985", "standoff", "sleeve")


def part_type(instance) -> str:
    return instance.part.split("/")[1]


def colour(instance):
    if instance.kind == "cable":
        return CABLE_COLOURS[instance.meta["colour"]]
    name = part_type(instance)
    if name in COLOURS:
        return COLOURS[name]
    if any(token in name for token in METAL):
        return (0.62, 0.62, 0.64)
    return GRAPHITE


def is_metal(instance) -> bool:
    return any(token in part_type(instance) for token in METAL)


def _sectioned(instance, plane_point, plane_normal):
    mesh = trimesh.load(instance.mesh, force="mesh").copy()
    mesh.apply_transform(instance.matrix)
    keep = -np.asarray(plane_normal, dtype=float)
    corners = trimesh.bounds.corners(mesh.bounds)
    side = (corners - plane_point) @ keep
    if np.all(side >= 0):
        return mesh
    if np.all(side < 0):
        return None
    cut = mesh.slice_plane(plane_point, keep, cap=True)
    return cut if cut is not None and len(cut.faces) else None


def objects(instances, style="beauty", highlight=(), hide=(), section=None):
    """Render-object dicts; `section=(point, normal)` removes material on the +normal side."""
    TMP.mkdir(parents=True, exist_ok=True)
    result = []
    for instance in instances:
        if instance.kind == "reference" or instance.id in hide or part_type(instance) in hide:
            continue
        role = "highlight" if (instance.id in highlight or part_type(instance) in highlight) else "context"
        if style == "beauty":
            role = "new"
        mesh_path = instance.mesh
        matrix = instance.matrix
        if section is not None:
            cut = _sectioned(instance, *section)
            if cut is None:
                continue
            key = hashlib.sha1(f"{instance.id}{instance.matrix.tobytes()}{section}".encode()).hexdigest()[:16]
            mesh_path = TMP / f"cut_{key}.stl"
            cut.export(mesh_path)
            matrix = np.eye(4)  # the cut mesh is already in world coordinates
        entry = {
            "mesh": str(mesh_path),
            "matrix": [float(v) for v in matrix.flatten()],
            "role": role,
            "name": instance.id,
            "metal": is_metal(instance),
        }
        if style == "beauty" or role == "highlight":
            entry["color"] = list(colour(instance)) if style == "beauty" else [1.0, 0.82, 0.25]
        result.append(entry)
    return result


def camera(target, azimuth_deg, elevation_deg, distance, ortho_scale=None, lens=50):
    az, el = math.radians(azimuth_deg), math.radians(elevation_deg)
    direction = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
    location = np.asarray(target, dtype=float) + distance * direction
    spec = {"location": location.tolist(), "target": list(map(float, target))}
    if ortho_scale is not None:
        spec.update(type="ORTHO", ortho_scale_mm=ortho_scale)
    else:
        spec.update(type="PERSP", lens_mm=lens)
    return spec


def run(renders: list[dict], name: str) -> None:
    job = REPO / f"build/render/{name}.json"
    job.parent.mkdir(parents=True, exist_ok=True)
    job.write_text(json.dumps({"renders": renders}))
    command = [blender_executable(), "-b", "--factory-startup", "-P", str(RENDER_JOB_SCRIPT), "--", str(job)]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0 or "Traceback" in completed.stdout + completed.stderr:
        sys.stderr.write(completed.stdout[-4000:] + completed.stderr[-4000:])
        raise RuntimeError(f"blender failed for {name}")
