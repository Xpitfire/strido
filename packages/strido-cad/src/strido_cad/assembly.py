"""Compose the full Strido assembly and pose it at arbitrary joint angles.

Sources of geometry (all in millimetres, placed in the upstream STEP frame):

1. upstream print STLs placed by `hardware/assembly/upstream_placements.yaml`,
2. purchased/printed solids that only exist in the upstream STEP (servos,
   bearings, horns, bushings, SBEC, the hip horn adapter and foot spacer),
3. new Strido parts and vendor models from `strido_cad.parts` / `strido_cad.vendor`
   (composed by `strido_cad.catalog`).

Every instance belongs to a rigid body (``base``, ``FL.hip``, ``FL.thigh``,
``FL.calf``, ``FL.crank``, ``FL.arm``, ``FL.short_link``, ``FL.long_link`` ...).
`pose()` moves bodies with the exact leg linkage from `strido.leg`, so every
check (interference, range of motion, LiDAR occlusion) runs on the real
mechanism instead of a simplified URDF.
"""

import math
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import trimesh
import yaml

from strido import leg as leg_kinematics
from strido.geometry import LEG_NAMES, LEGS

from .paths import CORRECTIONS, KINEMATICS, REPO, UPSTREAM_PLACEMENTS, UPSTREAM_STEP
from .step_cache import load_step_cache

PLACEMENTS = UPSTREAM_PLACEMENTS

LEG_PREFIX = {
    "FR": "Yertle Single v2/legs:1/fr leg_assem",
    "RR": "Yertle Single v2/legs:1/br leg_assem",
    "FL": "Yertle Single v2/legs(Mirror):1/fr leg_assem",
    "RL": "Yertle Single v2/legs(Mirror):1/br leg_assem",
}


@dataclass
class Instance:
    """One physical object in the robot."""

    id: str
    part: str  # catalog id (one per distinct purchasable/printable item)
    mesh: Path  # mesh file in millimetres
    matrix: np.ndarray  # mesh coordinates -> STEP world at the CAD reference pose
    body: str  # rigid body the instance moves with
    kind: str  # printed | purchased | fastener | reference
    meta: dict = field(default_factory=dict)


def _leg_of(path: str) -> str | None:
    for name, prefix in LEG_PREFIX.items():
        if path.startswith(prefix):
            return name
    return None


def _leg_body(path: str, leg: str) -> str:
    """Rigid body of a STEP leaf below a leg assembly."""
    relative = path[len(LEG_PREFIX[leg]) :]
    lowered = relative.lower()
    if "/leg v" not in lowered:
        if "servo_blue" in lowered:
            return "base"  # hip servo body is fixed in the frame
        return f"{leg}.hip"
    if "tibia" in lowered:
        return f"{leg}.calf"
    if "link rod v22" in lowered:
        return f"{leg}.long_link"
    if "28mm link rod" in lowered:
        return f"{leg}.short_link"
    if "arm metal standard" in lowered:
        return f"{leg}.arm"
    if "servo arm mod" in lowered:
        return f"{leg}.crank"
    if "femur" in lowered:
        return f"{leg}.thigh"
    if "servo arm round" in lowered:
        return f"{leg}.thigh"  # horn on the thigh servo output
    if "servo_blue" in lowered:
        return f"{leg}.hip"
    return f"{leg}.hip"


# STEP-only leaves we keep, mapped to catalog part ids. Order matters: first match wins.
STEP_KEEP = (
    ("servo_blue", "purchased/servo_spt5435lv", "purchased"),
    ("bearing_16m", "purchased/bearing_625zz", "purchased"),
    ("37mm bearing", "purchased/bearing_6805_2rs", "purchased"),
    ("bearing_13mm", "purchased/bearing_633zz", "purchased"),
    ("bushing", "purchased/sleeve_bearing_3x5x5_pair", "purchased"),
    ("arm metal standard", "purchased/servo_arm_horn_25t", "purchased"),
    ("servo arm round", "purchased/servo_disc_horn_25t", "purchased"),
    ("shoulder_joint_ball_bearing_pin", "printed/hip_bearing_pin", "printed"),
    ("ubec", "purchased/sbec_yep_20a", "purchased"),
)
# STEP-only solids that are printed parts without an upstream STL. They are
# exported to STL from the STEP (provenance: STEP).
STEP_PRINTED = (("tibia right", 2, "printed/foot_spacer"),)
# Not used: the STEP solid "servo holder3" (rear legs only) overlaps the current
# servo mounts by ~2860 mm^3 (60 % of its volume) - a stale body from an older
# revision; the published Left/Right_Servo_Mount carry the horn pocket directly.
# Leaves deliberately dropped: replaced by Strido parts or re-derived.
STEP_DROP = (
    "m3 screw",
    "socket button head",
    "raspberry pi",
    "rpi4",
    "pca9685",
    "turnigy",
    "10mm spacer",
    "rodend",
    "short rod",
)


def _stl_part_id(stl: str) -> str:
    return "printed/" + Path(stl).stem.lower()


def upstream_instances() -> list[Instance]:
    placements = yaml.safe_load(PLACEMENTS.read_text())
    instances = []
    for index, placement in enumerate(placements["placements"]):
        path = placement["step_path"]
        leg = _leg_of(path)
        body = _leg_body(path, leg) if leg else "base"
        part = _stl_part_id(placement["stl"])
        instances.append(
            Instance(
                id=f"{leg or 'body'}/{part.split('/')[1]}#{index}",
                part=part,
                mesh=REPO / placement["stl"],
                matrix=np.array(placement["matrix"]).reshape(4, 4),
                body=body,
                kind="printed",
                meta={"step_path": path, "source": "upstream STL"},
            )
        )

    cache = load_step_cache(UPSTREAM_STEP)
    grouped = {}
    for entry in cache:
        grouped.setdefault(entry["step_path"], []).append(entry)
    for path, entries in grouped.items():
        lowered = path.lower()
        leaf = path.split("/")[-1].lower()
        leg = _leg_of(path)
        body = _leg_body(path, leg) if leg else "base"
        if "=>[" in leaf:
            # Anonymous main solid of a sub-assembly: printed parts without STL live here.
            for needle, solid_index, part in STEP_PRINTED:
                if needle not in lowered:
                    continue
                for entry in entries:
                    if entry["solid"] == solid_index:
                        instances.append(
                            Instance(
                                id=f"{leg}/{part.split('/')[1]}",
                                part=part,
                                mesh=Path(entry["stl"]),
                                matrix=np.eye(4),
                                body=body,
                                kind="printed",
                                meta={"step_path": path, "source": "upstream STEP only"},
                            )
                        )
            continue
        if any(needle in lowered for needle in STEP_DROP):
            continue
        if "28mm link rod" in leaf:
            # Leaf = short link (has an STL) + its two sleeve-bearing pairs.
            for entry in entries:
                if entry["solid"] > 0:
                    instances.append(
                        Instance(
                            id=f"{leg}/sleeve_bearing_3x5x5_pair@{entry['key']}",
                            part="purchased/sleeve_bearing_3x5x5_pair",
                            mesh=Path(entry["stl"]),
                            matrix=np.eye(4),
                            body=body,
                            kind="purchased",
                            meta={"step_path": path, "source": "upstream STEP"},
                        )
                    )
            continue
        keep = [rule for rule in STEP_KEEP if rule[0] in leaf]
        if not keep:
            continue
        _, part, kind = keep[0]
        if len(entries) > 1:
            mesh_path = Path(entries[0]["stl"]).with_name(f"{entries[0]['key']}_merged.stl")
            if not mesh_path.is_file():
                trimesh.util.concatenate([trimesh.load(entry["stl"]) for entry in entries]).export(mesh_path)
        else:
            mesh_path = Path(entries[0]["stl"])
        instances.append(
            Instance(
                id=f"{leg or 'body'}/{part.split('/')[1]}@{entries[0]['key']}",
                part=part,
                mesh=mesh_path,
                matrix=np.eye(4),
                body=body,
                kind=kind,
                meta={"step_path": path, "source": "upstream STEP"},
            )
        )
    return apply_corrections(instances)


def correction_matrices() -> list[tuple[dict, dict[str, np.ndarray]]]:
    """Each correction of hardware/assembly/corrections.yaml with its STEP-frame matrix per leg."""
    corrections = yaml.safe_load(CORRECTIONS.read_text())["corrections"]
    frames = leg_frames()
    axes = {"thigh": lambda leg: (frames[leg].thigh_pivot, np.array([1.0, 0.0, 0.0]))}
    result = []
    for correction in corrections:
        per_leg = {}
        for leg in correction["legs"]:
            point, axis = axes[correction["axis"]](leg)
            per_leg[leg] = _rotation_about_line(point, axis, math.radians(correction["angle_deg"]))
        result.append((correction, per_leg))
    return result


def apply_corrections(instances: list[Instance]) -> list[Instance]:
    """Re-place the upstream parts listed in corrections.yaml (e.g. the right-leg horn pattern)."""
    corrected = list(instances)
    for correction, per_leg in correction_matrices():
        for index, instance in enumerate(corrected):
            leg = instance.body.split(".")[0]
            if (
                instance.part in correction["parts"]
                and leg in per_leg
                and instance.body == f"{leg}.{correction['body']}"
            ):
                corrected[index] = replace(
                    instance,
                    matrix=per_leg[leg] @ instance.matrix,
                    meta={**instance.meta, "correction": correction["id"]},
                )
    return corrected


# --------------------------------------------------------------------------- posing


def _rotation_about_line(point, axis, angle) -> np.ndarray:
    return trimesh.transformations.rotation_matrix(angle, axis, point)


def _translation(vector) -> np.ndarray:
    matrix = np.eye(4)
    matrix[:3, 3] = vector
    return matrix


@dataclass(frozen=True)
class LegFrames:
    """Measured axes of one leg in STEP coordinates."""

    hip_point: np.ndarray
    thigh_pivot: np.ndarray  # (x, y, z) on the thigh axis
    knee: np.ndarray
    drive: np.ndarray
    crank_pin_b: np.ndarray
    link_end: np.ndarray


def leg_frames() -> dict[str, LegFrames]:
    raw = yaml.safe_load(KINEMATICS.read_text())["legs_step_raw"]
    frames = {}
    for name in LEG_NAMES:
        leg = raw[name]
        x = leg["leg_plane_x_mm"]
        frames[name] = LegFrames(
            hip_point=np.array(leg["hip_axis_point_step_mm"]),
            thigh_pivot=np.array([x, *leg["femur_pivot_yz"]]),
            knee=np.array([x, *leg["knee_yz"]]),
            drive=np.array([x, *leg["drive_servo_yz"]]),
            crank_pin_b=np.array([x, *leg["crank_pin_b_yz"]]),
            link_end=np.array([x, *leg["tibia_link_end_yz"]]),
        )
    return frames


CAD_POSE = {name: (0.0, LEGS[name].cad_thigh_angle, LEGS[name].cad_calf_angle) for name in LEG_NAMES}


def _uv_to_step(frames: LegFrames, uv) -> np.ndarray:
    """Leg-plane (u forward, v up; metres, origin thigh pivot) -> STEP mm at the CAD hip angle."""
    return frames.thigh_pivot + np.array([0.0, -uv[0] * 1000.0, uv[1] * 1000.0])


def body_transforms(joints: dict[str, tuple[float, float, float]]) -> dict[str, np.ndarray]:
    """Rigid transforms (STEP frame, applied to CAD-pose geometry) of every body."""
    frames = leg_frames()
    transforms = {"base": np.eye(4)}
    x_axis = np.array([1.0, 0.0, 0.0])
    for name in LEG_NAMES:
        frame = frames[name]
        geometry = LEGS[name]
        hip, thigh, calf = joints.get(name, CAD_POSE[name])
        crank = leg_kinematics.crank_from_calf(name, thigh, calf)
        if crank is None:
            raise ValueError(f"{name}: linkage cannot reach thigh={thigh:.3f} calf={calf:.3f}")
        # Hip: +q1 about base +x == STEP -y.
        hip_transform = _rotation_about_line(frame.hip_point, np.array([0.0, -1.0, 0.0]), hip)
        thigh_local = _rotation_about_line(frame.thigh_pivot, x_axis, thigh - geometry.cad_thigh_angle)
        thigh_transform = hip_transform @ thigh_local
        knee_after_thigh = (thigh_local @ np.append(frame.knee, 1.0))[:3]
        calf_local = _rotation_about_line(knee_after_thigh, x_axis, calf - geometry.cad_calf_angle)
        transforms[f"{name}.hip"] = hip_transform
        transforms[f"{name}.thigh"] = thigh_transform
        transforms[f"{name}.calf"] = hip_transform @ calf_local @ thigh_local
        crank_delta = crank - geometry.cad_crank_angle
        transforms[f"{name}.crank"] = hip_transform @ _rotation_about_line(frame.thigh_pivot, x_axis, -crank_delta)
        transforms[f"{name}.arm"] = hip_transform @ _rotation_about_line(frame.drive, x_axis, -crank_delta)
        arm_now = np.array([geometry.drive_u, geometry.drive_v]) + geometry.arm_radius * np.array(
            [math.cos(crank), math.sin(crank)]
        )
        arm_cad = np.array([geometry.drive_u, geometry.drive_v]) + geometry.arm_radius * np.array(
            [math.cos(geometry.cad_crank_angle), math.sin(geometry.cad_crank_angle)]
        )
        transforms[f"{name}.short_link"] = hip_transform @ _translation(
            _uv_to_step(frame, arm_now) - _uv_to_step(frame, arm_cad)
        )
        points = leg_kinematics.linkage_points(name, thigh, calf)
        start_now = _uv_to_step(frame, points["crank_b"])
        end_now = _uv_to_step(frame, points["tibia_pin"])
        start_cad, end_cad = frame.crank_pin_b, frame.link_end
        angle_cad = math.atan2(end_cad[2] - start_cad[2], end_cad[1] - start_cad[1])
        angle_now = math.atan2(end_now[2] - start_now[2], end_now[1] - start_now[1])
        link_motion = (
            _translation(start_now)
            @ trimesh.transformations.rotation_matrix(angle_now - angle_cad, x_axis)
            @ _translation(-start_cad)
        )
        transforms[f"{name}.long_link"] = hip_transform @ link_motion
    return transforms


def posed(instances: list[Instance], joints: dict[str, tuple[float, float, float]]) -> list[Instance]:
    transforms = body_transforms(joints)
    return [replace(item, matrix=transforms[item.body] @ item.matrix) for item in instances]


def step_to_base() -> np.ndarray:
    """4x4 transform STEP mm -> robot base frame mm (REP-103)."""
    data = yaml.safe_load(KINEMATICS.read_text())["base_frame"]
    matrix = np.eye(4)
    rotation = np.array(data["rotation_step_to_base"])
    matrix[:3, :3] = rotation
    matrix[:3, 3] = -rotation @ np.array(data["origin_in_step_mm"])
    return matrix


_MESH_CACHE: dict[Path, trimesh.Trimesh] = {}


def load_mesh(path: Path) -> trimesh.Trimesh:
    if path not in _MESH_CACHE:
        _MESH_CACHE[path] = trimesh.load(path, force="mesh")
    return _MESH_CACHE[path]


def world_mesh(instance: Instance) -> trimesh.Trimesh:
    mesh = load_mesh(instance.mesh).copy()
    mesh.apply_transform(instance.matrix)
    return mesh
