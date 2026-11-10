"""Compose upstream instances with every Strido module into one instance list.

Built meshes are cached under build/cad/parts and build/cad/vendor. The meshes live at fixed paths,
so the cache is valid only for the source digest of the build that wrote them last.
"""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import trimesh

from . import assembly, fastener_meshes, fasteners, hole_stacks, long_link, parts, vendor, wiring, wiring_geometry
from .assembly import Instance
from .geom import boolean, cylinder, rotation, to_manifold, to_mesh, translation
from .paths import CAD_CACHE, CORRECTIONS, FASTENER_CATALOGUE, KINEMATICS, UPSTREAM_FASTENERS_JSON, UPSTREAM_PLACEMENTS

HERE = Path(__file__).resolve().parent
CACHE = CAD_CACHE / "parts"
BATTERY_MATRIX = translation((-28.5 + 47.0, 10.8 - 69.0, 34.7)) @ trimesh.transformations.rotation_matrix(
    np.pi / 2, (0, 0, 1)
)
# Two Hobbywing UBEC-10A (6.0 V) stand on edge in the side pockets left and right of the battery (the
# pockets are symmetric about x=-5 and end at the hip servos): +x feeds the front servo bus, -x the rear.
# Local box x (45) -> world y, local y (20) -> world z, local z (16.2) -> world x.
UBEC_AXES = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=float)
UBEC_MATRICES = (translation((19.2, -28.0, 37.6)) @ UBEC_AXES, translation((-45.4, -10.0, 37.6)) @ UBEC_AXES)
SIDE_STRIP_ITEMS = (
    # vendor id, matrix, label  (cable-tied / foam-taped items on the deck side strips)
    (
        "pololu_power_switch_hp",
        translation((-52.0, -30.0, parts.PLATE_TOP_Z + 1.0)),
        "Pololu pushbutton power switch (foam tape)",
    ),
)
# Power entry (hardware/wiring.yaml routes the wires between them):
# * main 25 A fuse: in-line ATO holder lying in the rear cavity above the WAGO bus, its leads running
#   out through the inner (battery side) and outer (back shell) frame openings; tied to the upper
#   shoulder frame. Holder frame: leads along local x, 32.2 mm lid across local y.
# * logic 7.5 A fuse: second holder in the back shell, between the arming jack and the button.
# * battery input: XT60H (sockets) on the robot pigtail, in the pocket beside the battery under the
#   deck, hood towards the battery's lead end (rear).
POWER_ITEMS = (
    (
        "fuse_holder_ato",
        translation((-5.0, 126.0, 87.0)) @ rotation([(0, 1, 0), (1, 0, 0), (0, 0, -1)]),
        "25 A main fuse, in-line ATO holder (rear cavity, tied to the upper shoulder frame)",
        "rear cavity",
    ),
    (
        "fuse_holder_ato",
        translation((5.0, 183.5, 62.3)),
        "7.5 A logic fuse, in-line ATO holder (back shell)",
        "rear panel",
    ),
    (
        "xt60h_female",
        translation((29.0, 52.0, 43.0)) @ rotation([(1, 0, 0), (0, 0, 1), (0, -1, 0)]),
        "XT60H-F battery input (robot pigtail, under the deck)",
        "battery bay",
    ),
)


def _source_digest() -> str:
    """Hash of everything the cached part meshes and manifest are built from: the part/vendor code,
    this module's placements, and the upstream placement data the new parts are cut against."""
    digest = hashlib.sha256()
    sources = [
        HERE / name for name in ("parts.py", "vendor.py", "geom.py", "catalog.py", "assembly.py", "long_link.py")
    ]
    sources += [UPSTREAM_PLACEMENTS, CORRECTIONS, KINEMATICS, FASTENER_CATALOGUE, wiring.SOURCE]
    for source in sources:
        digest.update(source.read_bytes())
    return digest.hexdigest()[:12]


def modules():
    return [
        parts.front_display_module(),
        parts.top_sensor_module(),
        parts.camera_module(),
        parts.back_module(),
        parts.deck_module(),
        parts.cavity_module("front"),
        parts.cavity_module("rear"),
    ]


def build_parts() -> dict:
    """Build (or load cached) new parts and the placement manifest."""
    digest = _source_digest()
    manifest_path = CACHE / "manifest.json"
    if manifest_path.is_file():
        cached = json.loads(manifest_path.read_text())
        if cached["digest"] == digest:  # meshes on disk were written by this very source
            return cached
    CACHE.mkdir(parents=True, exist_ok=True)
    manifest_path.unlink(missing_ok=True)  # an interrupted rebuild must not leave a stale manifest behind
    vendor_parts = vendor.build_all()
    manifest = {"digest": digest, "parts": [], "vendors": [], "fasteners": [], "modules": []}
    for module in modules():
        manifest["modules"].append(module.name)
        for part in module.parts:
            path = CACHE / f"{part.part.split('/')[1]}.stl"
            part.mesh.export(path)
            manifest["parts"].append(
                {
                    "part": part.part,
                    "title": part.title,
                    "mesh": str(path),
                    "body": part.body,
                    "module": module.name,
                    "print_down": part.print_down,
                    "replaces": part.replaces,
                    "material": part.material,
                    "infill_percent": part.infill_percent,
                    "supports": part.supports,
                    "note": part.note,
                    "volume_mm3": float(part.mesh.volume),
                }
            )
        for placement in module.vendors:
            mesh = vendor.OUT / f"{placement.vendor_id}.stl"
            assert mesh.is_file(), placement.vendor_id
            manifest["vendors"].append(
                {
                    "vendor": placement.vendor_id,
                    "mesh": str(mesh),
                    "matrix": placement.matrix.tolist(),
                    "body": placement.body,
                    "label": placement.label,
                    "module": module.name,
                    "official": vendor_parts[placement.vendor_id].official
                    if placement.vendor_id in vendor_parts
                    else False,
                }
            )
        for fastener in module.fasteners:
            manifest["fasteners"].append(
                {
                    "spec": fastener.spec,
                    "head": list(map(float, fastener.head)),
                    "axis": list(map(float, fastener.axis)),
                    "body": fastener.body,
                    "joint": fastener.joint,
                    "module": module.name,
                }
            )
    for vendor_id, matrix, label in SIDE_STRIP_ITEMS:
        manifest["vendors"].append(
            {
                "vendor": vendor_id,
                "mesh": str(vendor.OUT / f"{vendor_id}.stl"),
                "matrix": matrix.tolist(),
                "body": "base",
                "label": label,
                "module": "electronics deck",
                "official": True,
            }
        )
    for vendor_id, matrix, label, module_name in POWER_ITEMS:
        manifest["vendors"].append(
            {
                "vendor": vendor_id,
                "mesh": str(vendor.OUT / f"{vendor_id}.stl"),
                "matrix": matrix.tolist(),
                "body": "base",
                "label": label,
                "module": module_name,
                "official": vendor_parts[vendor_id].official,
            }
        )
    for name, spec in wiring.nodes(wiring.load()).items():  # adhesive tie mounts under wiring tie nodes
        if "mount" in spec:
            matrix = trimesh.geometry.align_vectors([0, 0, 1], spec["mount"]["normal"])
            matrix[:3, 3] = spec["mount"]["at"]
            manifest["vendors"].append(
                {
                    "vendor": "cable_tie_mount",
                    "mesh": str(vendor.OUT / "cable_tie_mount.stl"),
                    "matrix": matrix.tolist(),
                    "body": "base",
                    "label": f"adhesive cable-tie mount ({name})",
                    "module": "electronics deck",
                    "official": False,
                }
            )
    for index, matrix in enumerate(UBEC_MATRICES):
        manifest["vendors"].append(
            {
                "vendor": "hobbywing_ubec_10a",
                "mesh": str(vendor.OUT / "hobbywing_ubec_10a.stl"),
                "matrix": matrix.tolist(),
                "body": "base",
                "label": f"servo UBEC 6.0 V ({'front' if index == 0 else 'rear'} legs, foam tape)",
                "module": "battery bay",
                "official": False,
            }
        )
    manifest["vendors"].append(
        {
            "vendor": "lipo_2s_5000_gensace",
            "mesh": str(vendor.OUT / "lipo_2s_5000.stl"),
            "matrix": BATTERY_MATRIX.tolist(),
            "body": "base",
            "label": "2S 5000 mAh LiPo",
            "module": "battery bay",
            "official": False,
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=1))
    return manifest


def full_assembly() -> list[Instance]:
    """Upstream mechanics + Strido additions (new parts, vendor models, fasteners, wiring harness)."""
    return strido_instances(assembly.upstream_instances())


def strido_instances(base: list[Instance]) -> list[Instance]:
    manifest = build_parts()
    replaced = {entry["replaces"] for entry in manifest["parts"] if entry["replaces"]}
    instances = []
    for item in base:
        if item.part in replaced:
            continue
        if item.part == "purchased/sbec_yep_20a":  # replaced by two Hobbywing UBEC-10A (UBEC_MATRICES)
            continue
        instances.append(item)
    for entry in manifest["parts"]:
        instances.append(
            Instance(
                entry["part"].split("/")[1],
                entry["part"],
                Path(entry["mesh"]),
                np.eye(4),
                entry["body"],
                "printed",
                {"source": "strido", "module": entry["module"]},
            )
        )
    for index, entry in enumerate(manifest["vendors"]):
        keepout = entry["vendor"].endswith("_keepout")
        instances.append(
            Instance(
                f"{entry['vendor']}#{index}",
                f"{'reference' if keepout else 'purchased'}/{entry['vendor']}",
                Path(entry["mesh"]),
                np.array(entry["matrix"]),
                entry["body"],
                "reference" if keepout else "purchased",
                {"label": entry["label"], "module": entry["module"], "official": entry["official"]},
            )
        )
    for index, entry in enumerate(manifest["fasteners"]):
        instances.append(
            Instance(
                f"{entry['spec']}#{index}",
                f"fastener/{entry['spec']}",
                fastener_meshes.mesh_path(entry["spec"]),
                fastener_meshes.placement(entry["head"], entry["axis"]),
                entry["body"],
                "fastener",
                {"joint": entry["joint"], "module": entry["module"]},
            )
        )
    upstream_placements = upstream_fastener_placements(manifest["fasteners"])
    for index, entry in enumerate(upstream_placements):
        instances.append(
            Instance(
                f"{entry['spec']}#u{index}",
                f"fastener/{entry['spec']}",
                fastener_meshes.mesh_path(entry["spec"]),
                fastener_meshes.placement(entry["head"], entry["axis"]),
                entry["body"],
                "fastener",
                {"joint": entry["joint"], "source": "upstream joint"},
            )
        )
    instances = derive_upstream_parts(instances, upstream_placements)
    instances = long_link.replace_long_links(instances)  # ADR-010: stiff long link
    return instances + wiring_geometry.instances(instances)  # cables, sleeves, ties, tie mounts


UPSTREAM_FASTENERS = UPSTREAM_FASTENERS_JSON
# Upstream parts that Strido re-drills where an instance's joint axis runs into solid material.
# Servo mounts: one STL serves a front and a rear leg; only the rear-leg face carries the hip-pivot
# pilot, so the front legs get a variant with a pilot along their (different) pivot axis.
DERIVED_PILOTS = {
    "printed/left_servo_mount": {"joint": "hip_pivot", "radius_mm": 1.25, "depth_mm": 12.0},
    "printed/right_servo_mount": {"joint": "hip_pivot", "radius_mm": 1.25, "depth_mm": 12.0},
}
PROBE_RADIUS_MM = 0.5


def _blocked(mesh: trimesh.Trimesh, head: np.ndarray, axis: np.ndarray, depth: float) -> bool:
    """True when the screw path (thin probe cylinder) runs through material of `mesh`."""
    probe = to_manifold(to_mesh(cylinder(tuple(head), tuple(axis), PROBE_RADIUS_MM, 0.0, depth)))
    return (to_manifold(mesh) ^ probe).volume() > 0.5


def derive_upstream_parts(instances: list[Instance], placements: list[dict]) -> list[Instance]:
    """Give every DERIVED_PILOTS instance whose joint screw hits solid material its own re-drilled variant."""
    screw_specs = {spec for spec, item in fastener_meshes.CATALOGUE["items"].items() if item["kind"] == "screw"}
    result = list(instances)
    for part, spec in DERIVED_PILOTS.items():
        for index, item in enumerate(result):
            if item.part != part:
                continue
            source = assembly.load_mesh(item.mesh)
            inverse = np.linalg.inv(item.matrix)
            axes = []
            for entry in placements:
                if entry["joint"] == spec["joint"] and entry["body"] == item.body and entry["spec"] in screw_specs:
                    head = (inverse @ np.append(entry["head"], 1.0))[:3]
                    axis = inverse[:3, :3] @ np.array(entry["axis"])
                    if _blocked(source, head, axis, spec["depth_mm"]):
                        axes.append((head, axis))
            if not axes:
                continue
            leg = item.body.split(".")[0]
            name = f"{part.split('/')[1]}_{leg.lower()}"
            target = CACHE / f"{name}.stl"
            key = json.dumps([str(item.mesh), spec, [(h.round(3).tolist(), a.round(5).tolist()) for h, a in axes]])
            stamp = CACHE / f"{name}.key"
            if not target.is_file() or not stamp.is_file() or stamp.read_text() != key:
                CACHE.mkdir(parents=True, exist_ok=True)
                cuts = [cylinder(tuple(h), tuple(a), spec["radius_mm"], 0.0, spec["depth_mm"]) for h, a in axes]
                boolean(source, cut=cuts).export(target)
                stamp.write_text(key)
            result[index] = replace(
                item,
                part=f"printed/{name}",
                mesh=target,
                meta={
                    **item.meta,
                    "source": "strido derived",
                    "derived_from": part,
                    "derived_note": f"upstream {part.split('/')[1]} + Ø{2 * spec['radius_mm']:.1f} mm "
                    f"{spec['joint'].replace('_', ' ')} pilot for the {leg} leg",
                },
            )
    return result


def upstream_fastener_placements(new_fasteners: list[dict]) -> list[dict]:
    """Upstream joint fasteners, minus joints whose screws a Strido part replaces (same axis)."""
    if not UPSTREAM_FASTENERS.is_file():
        hole_stacks.main()
        fasteners.main()
    placements = json.loads(UPSTREAM_FASTENERS.read_text())["placements"]
    kept = []
    for entry in placements:
        head, axis = np.array(entry["head"]), np.array(entry["axis"])
        replaced = False
        for new in new_fasteners:
            offset = np.array(new["head"]) - head
            lateral = offset - np.dot(offset, axis) * axis
            if abs(abs(np.dot(np.array(new["axis"]), axis)) - 1) < 1e-3 and np.linalg.norm(lateral) < 1.0:
                replaced = True
                break
        if not replaced:
            kept.append(entry)
    return kept
