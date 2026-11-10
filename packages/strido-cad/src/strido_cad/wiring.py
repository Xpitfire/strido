"""Wiring harness in the CAD: every cable of hardware/wiring.yaml routed through the assembly.

hardware/wiring.yaml is the single source of the wiring. This module turns it into geometry:

* every cable becomes one or more *runs* (a servo lead splits into a power pair to the WAGO bus
  and a signal wire to the PCA9685) from an anchor through route nodes to an anchor
  (`wiring_anchors`);
* consecutive points on the same rigid body are joined by straight, rigid segments; points on two
  bodies (a lead crossing the hip joint) are joined by a flexible *loop* of the length the YAML
  prescribes, drawn as a circular arc bowed along the node's ``bulge``;
* route nodes ending in ``.L`` are mirrored to ``.R`` about the body's mid-plane, so left and right
  legs share one route; ``{bay}``/``{side}`` in servo-lead routes expand per leg;
* segments shared by three or more runs are drawn as one spiral-wrapped bundle sleeve, and every
  node with ``tie`` gets a cable tie.

`instances(assembly)` returns the cables as `Instance`s of kind ``cable`` (meta: run, type, colour,
flex, length). The wiring gate (`strido_verify.wiring`) checks reach, loop slack, bends, ports,
consumption and clearance on the `runs()` this module builds.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from strido import leg as leg_kinematics
from strido.geometry import LEG_NAMES, LEGS

from . import wiring_router
from .assembly import Instance
from .paths import CAD_CACHE, HARDWARE, JOINT_LIMITS
from .wiring_anchors import Anchor, AnchorResolver

HERE = Path(__file__).resolve().parent
SOURCE = HARDWARE / "wiring.yaml"
ELECTRONICS = HARDWARE / "electronics.yaml"
CACHE = CAD_CACHE / "wiring"
MIRROR_X = -5.0  # the body is symmetric about x = -5 mm (STEP frame)
LEG_OF = {("front", "L"): "FL", ("front", "R"): "FR", ("rear", "L"): "RL", ("rear", "R"): "RR"}
BUNDLE_PACKING = 1.15  # bundle diameter = 1.15 * sqrt(sum d^2) (round wires, loosely packed)


def load() -> dict:
    return yaml.safe_load(SOURCE.read_text())


@dataclass(frozen=True)
class Point:
    name: str
    xyz: np.ndarray  # STEP mm, CAD reference pose
    body: str
    tie: str | None = None
    loop_mm: float | None = None  # free length from this point to the next (other body)
    bulge: np.ndarray | None = None


@dataclass
class Run:
    cable: str
    name: str
    type: str
    conductors: int
    points: list[Point]
    carries: str | None = None
    sleeve: bool = False  # spiral-wrapped along its whole route even when it runs alone

    def segments(self):
        return list(zip(self.points[:-1], self.points[1:]))


# --------------------------------------------------------------------------- nodes and expansion
def _mirror(spec: dict) -> dict:
    mirrored = dict(spec)
    x, y, z = spec["at"]
    mirrored["at"] = [2 * MIRROR_X - x, y, z]
    if "bulge" in spec:
        bx, by, bz = spec["bulge"]
        mirrored["bulge"] = [-bx, by, bz]
    return mirrored


def nodes(data: dict) -> dict[str, dict]:
    table = {}
    for name, spec in data["nodes"].items():
        table[name] = spec
        if name.endswith(".L"):
            table[name[:-2] + ".R"] = _mirror(spec)
    return table


def _node_point(name: str, spec: dict) -> Point:
    body = spec.get("body", "base")
    if body == "hip":
        bay, side = name.split(".")[0], name.rsplit(".", 1)[1]
        body = f"{LEG_OF[(bay, side)]}.hip"
    bulge = np.asarray(spec["bulge"], dtype=float) if "bulge" in spec else None
    return Point(name, np.asarray(spec["at"], dtype=float), body, spec.get("tie"), spec.get("loop_mm"), bulge)


def _anchor_points(anchor: Anchor, stubs: dict, leaving: bool) -> list[Point]:
    """The anchor and a short straight lead-out along its exit direction."""
    kind = anchor.name.split(":")[0] if ":" in anchor.name else "default"
    tip = Point(anchor.name, anchor.point, anchor.body)
    stub = Point(f"{anchor.name}+", anchor.point + anchor.out * stubs.get(kind, stubs["default"]), anchor.body)
    return [tip, stub] if leaving else [stub, tip]


def _fill(names: list[str], values: dict) -> list[str]:
    """Route node names of a servo-lead template for one leg ({bay}, {side}, {wago})."""
    return [name.format(**values) for name in names]


def _servo_cables(data: dict) -> list[dict]:
    spec = data["servo_leads"]
    channels = yaml.safe_load(ELECTRONICS.read_text())["servos"]["channels"]
    cables = []
    for leg, joints in channels.items():
        bay, side, wago = spec["bay"][leg], "L" if leg.endswith("L") else "R", spec["wago_bay"][leg]
        for joint, channel in joints.items():
            route = spec["route"][joint]
            values = {"bay": bay, "side": side, "wago": wago}
            cables.append(
                {
                    "id": f"S-{leg}-{joint}",
                    "type": spec["type"],
                    "from": f"servo:{leg}.{joint}",
                    "via": _fill(route["trunk"], values),
                    "branches": [
                        {
                            "name": "power",
                            "type": spec["power_type"],
                            "via": _fill(route["power"], values),
                            "to": f"wago:{bay}.{wago}.p{spec['wago_port'][joint]}",
                        },
                        {
                            "name": "signal",
                            "type": spec["signal_type"],
                            "via": _fill(route["signal"], values),
                            "to": f"pca:{channel}",
                        },
                    ],
                }
            )
    return cables


def cable_specs(data: dict) -> list[dict]:
    return data["cables"] + _servo_cables(data)


def runs(assembly: list[Instance], data: dict | None = None) -> list[Run]:
    """Every run through its anchors and route nodes (legs between base nodes not yet routed)."""
    data = data or load()
    resolver = AnchorResolver(assembly, data["anchors"])
    table = nodes(data)
    types = data["cable_types"]
    stub = data["anchor_stub_mm"]
    result = []
    for cable in cable_specs(data):
        via = [_node_point(n, table[n]) for n in cable.get("via", [])]
        if "cores" in cable:  # conductors with their own ends (a jumper per WAGO rail, a lead split at its plug)
            for core in cable["cores"]:
                points = _anchor_points(resolver.resolve(core["from"]), stub, leaving=True) + via
                points += _anchor_points(resolver.resolve(core["to"]), stub, leaving=False)
                name = f"{cable['id']}/{core['name']}"
                result.append(Run(cable["id"], name, core["type"], 1, points, cable.get("carries")))
            continue
        start = _anchor_points(resolver.resolve(cable["from"]), stub, leaving=True)
        trunk = start + via
        if "branches" not in cable:
            end = _anchor_points(resolver.resolve(cable["to"]), stub, leaving=False)
            kind = types[cable["type"]]
            result.append(
                Run(
                    cable["id"],
                    cable["id"],
                    cable["type"],
                    kind["conductors"],
                    trunk + end,
                    cable.get("carries"),
                    cable.get("sleeve", False),
                )
            )
            continue
        result.append(Run(cable["id"], f"{cable['id']}", cable["type"], types[cable["type"]]["conductors"], trunk))
        for branch in cable["branches"]:
            points = [trunk[-1]] + [_node_point(n, table[n]) for n in branch["via"]]
            points += _anchor_points(resolver.resolve(branch["to"]), stub, leaving=False)
            kind = types[branch["type"]]
            result.append(
                Run(cable["id"], f"{cable['id']}/{branch['name']}", branch["type"], kind["conductors"], points)
            )
    return result


def _routed_leg(a: Point, b: Point) -> bool:
    """Legs between two base points are routed, except an anchor's straight lead-out."""
    stub = a.name == f"{b.name}+" or b.name == f"{a.name}+"
    return a.body == "base" and b.body == "base" and not stub


def bundle_diameter(diameters: list[float]) -> float:
    if len(diameters) == 1:
        return diameters[0]
    return BUNDLE_PACKING * float(np.sqrt(np.sum(np.square(diameters))))


def ring_radius(kind: dict) -> float:
    """Radius of the circle the conductors of a round multi-core cable sit on (three or more drawn cores)."""
    count = len(kind["colours"])
    return kind["od_mm"] / (2 * np.sin(np.pi / count))


def run_diameter(run: Run, types: dict) -> float:
    """Envelope of a run as drawn: one core its diameter; a pair or a flat ribbon side by side; three
    or more round cores on a ring."""
    kind = types[run.type]
    count = len(kind["colours"])
    if count == 1:
        return kind["od_mm"]
    if kind.get("flat") or count == 2:
        return (count - 1) * kind["strand_mm"] + kind["od_mm"]
    return 2 * ring_radius(kind) + kind["od_mm"]


def route_runs(raw: list[Run], occupancy: wiring_router.Occupancy, types: dict) -> list[Run]:
    """Replace every routed leg by the router's path; runs sharing a leg share its geometry."""
    legs = {}
    for run in raw:
        for a, b in run.segments():
            if _routed_leg(a, b):
                key = tuple(sorted((a.name, b.name)))
                legs.setdefault(key, {"ends": {a.name: a, b.name: b}, "diameters": []})["diameters"].append(
                    run_diameter(run, types)
                )
    paths = {}
    for key, leg in sorted(legs.items()):
        a, b = leg["ends"][key[0]], leg["ends"][key[1]]
        radius = bundle_diameter(leg["diameters"]) / 2
        path = wiring_router.route(occupancy, a.xyz, b.xyz, radius)
        paths[key] = [Point(f"{key[0]}~{key[1]}~{k}", p, "base") for k, p in enumerate(path[1:-1])]
    routed = []
    for run in raw:
        points = [run.points[0]]
        for a, b in run.segments():
            if _routed_leg(a, b):
                key = tuple(sorted((a.name, b.name)))
                middle = paths[key] if key[0] == a.name else paths[key][::-1]
                points += middle
            points.append(b)
        routed.append(Run(run.cable, run.name, run.type, run.conductors, points, run.carries, run.sleeve))
    return routed


def stand_pose() -> dict[str, tuple[float, float, float]]:
    """Foot 170 mm below the hip (the CAD reference for the hip-only sweep)."""
    result = {}
    for name in LEG_NAMES:
        leg = LEGS[name]
        foot = np.array([leg.hip_x, leg.hip_y + leg.thigh_offset_y, -0.17])
        result[name] = tuple(leg_kinematics.inverse_kinematics(name, foot))
    return result


def mesh_stamp(mesh: Path) -> bytes:
    """Cache-key part for a mesh file: path, size and modification time (a part re-shaped in place rewrites it)."""
    stat = Path(mesh).stat()
    return f"{mesh}:{stat.st_size}:{stat.st_mtime_ns}".encode()


def occupancy(assembly: list[Instance]) -> wiring_router.Occupancy:
    digest = hashlib.sha256(JOINT_LIMITS.read_bytes() + (HERE / "wiring_router.py").read_bytes())
    for item in assembly:
        if item.kind != "cable":
            digest.update(item.id.encode() + mesh_stamp(item.mesh) + item.matrix.tobytes())
    key = digest.hexdigest()[:12]
    path = CACHE / f"occupancy-{key}.npz"
    if path.is_file():
        stored = np.load(path)
        return wiring_router.Occupancy(stored["low"], tuple(stored["shape"]), stored["occupied"])
    CACHE.mkdir(parents=True, exist_ok=True)
    for old in CACHE.glob("occupancy-*.npz"):
        old.unlink()
    grid = wiring_router.build(assembly, stand_pose())
    np.savez_compressed(path, low=grid.low, shape=np.array(grid.shape), occupied=grid.occupied)
    return grid


def routed(assembly: list[Instance], data: dict | None = None) -> list[Run]:
    data = data or load()
    return route_runs(runs(assembly, data), occupancy(assembly), data["cable_types"])
