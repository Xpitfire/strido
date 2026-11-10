"""Where cables leave their devices: anchor points resolved against the assembled CAD.

An anchor is a point in the STEP frame (mm, CAD reference pose), the direction the cable leaves
in and the rigid body it moves with. hardware/wiring.yaml names anchors in four ways:

* ``servo:FL.thigh``: the lead exit of a servo, derived from its mesh (the SPT5435LV lead leaves
  through a grommet in the bottom cap at the output-shaft end, `SERVO_LEAD`);
* ``wago:front.0.p2``: port 2 (0..4) of the WAGO pair (V+ above GND) in bay 0 or 1 of a cavity;
  the anchor sits between the two wire entries, so a red/black pair lands in both connectors;
  ``wago:front.0.p2.GND`` / ``.V+`` is the entry of one connector (a single wire);
* ``pca:11``: the top of the servo plug on PCA9685 channel 11;
* a name from the ``anchors:`` table: a point in the canonical frame of a vendor part
  (``vendor`` + ``local`` + ``out``, optional ``match`` on the placement label) or a fixed
  ``at`` point on a body.
"""

from dataclasses import dataclass

import numpy as np

from .assembly import Instance, load_mesh

SERVO_HEIGHT_MM = 44.5  # case + output spline (SPT drawing)
SERVO_LENGTH_MM = 56.0  # over the mounting ears
SERVO_CASE_LENGTH_MM = 40.0
# Lead exit: grommet in the bottom cap, at the end face next to the output shaft (SPT5435LV-180W
# product photo, Reacher listing); the grommet centre sits ~5 mm above the bottom face.
SERVO_LEAD = {"above_bottom_mm": 5.0}
# WAGO 221-415 canonical frame (vendor.wago_221_415): 30 x 18.8 x 8.4 box, the five wire entries
# on the y=0 face at 6 mm pitch, centred 3.2 mm above the base.
WAGO_PORT_X = tuple(3.0 + 6.0 * i for i in range(5))
WAGO_PORT_Z = 3.2
# Adafruit PCA9685 (815) canonical frame: four groups of four 3-pin headers along the front edge;
# a plugged JR housing ends 15.5 mm above the header base (vendor.pca9685_plug_keepout).
PCA_CHANNEL_X0 = 11.4
PCA_PITCH = 2.54
PCA_PLUG_TOP_Z = 10.1 + 15.5
PCA_PLUG_Y = 5.0


@dataclass(frozen=True)
class Anchor:
    name: str
    point: np.ndarray
    out: np.ndarray
    body: str


def _unit(vector) -> np.ndarray:
    vector = np.asarray(vector, dtype=float)
    return vector / np.linalg.norm(vector)


def _world(instance: Instance, local, out) -> tuple[np.ndarray, np.ndarray]:
    matrix = instance.matrix
    point = matrix[:3, :3] @ np.asarray(local, dtype=float) + matrix[:3, 3]
    return point, _unit(matrix[:3, :3] @ np.asarray(out, dtype=float))


def servo_lead_exit(instance: Instance) -> tuple[np.ndarray, np.ndarray]:
    """Lead exit point and direction of one placed SPT5435LV (upstream meshes are in world coordinates)."""
    vertices = load_mesh(instance.mesh).vertices @ instance.matrix[:3, :3].T + instance.matrix[:3, 3]
    low, high = vertices.min(axis=0), vertices.max(axis=0)
    extent = high - low
    shaft_axis = int(np.argmin(np.abs(extent - SERVO_HEIGHT_MM)))
    long_axis = int(np.argmin(np.abs(extent - SERVO_LENGTH_MM)))
    ends = {}
    for sign, face in ((1.0, high[shaft_axis]), (-1.0, low[shaft_axis])):
        near = vertices[np.abs(vertices[:, shaft_axis] - face) < 2.5]
        ends[sign] = (np.ptp(near[:, long_axis]), near.mean(axis=0))
    spline_sign = min(ends, key=lambda s: ends[s][0])  # the spline end is the narrow one
    spline = ends[spline_sign][1]
    centre = (low + high) / 2
    shaft_end = float(np.sign(spline[long_axis] - centre[long_axis]))
    point = centre.copy()
    point[long_axis] = centre[long_axis] + shaft_end * SERVO_CASE_LENGTH_MM / 2
    bottom = low[shaft_axis] if spline_sign > 0 else high[shaft_axis]
    point[shaft_axis] = bottom + spline_sign * SERVO_LEAD["above_bottom_mm"]
    out = np.zeros(3)
    out[long_axis] = shaft_end
    return point, out


def _centre(instance: Instance) -> np.ndarray:
    return instance.matrix[:3, :3] @ load_mesh(instance.mesh).bounds.mean(axis=0) + instance.matrix[:3, 3]


def servo_instances(instances: list[Instance]) -> dict[str, Instance]:
    """'FL.hip' / 'FL.thigh' / 'FL.calf' -> servo instance. The hip servo sits on the base; of the two
    servos on the hip body, the thigh servo drives the thigh disc horn."""
    found = {}
    for leg in ("FL", "FR", "RL", "RR"):
        servos = [i for i in instances if i.part == "purchased/servo_spt5435lv" and i.id.startswith(f"{leg}/")]
        horn = next(i for i in instances if i.body == f"{leg}.thigh" and "servo_disc_horn" in i.part)
        on_hip = [s for s in servos if s.body == f"{leg}.hip"]
        assert len(on_hip) == 2 and len(servos) == 3, leg
        on_hip.sort(key=lambda s: np.linalg.norm(_centre(s) - _centre(horn)))
        found[f"{leg}.hip"] = next(s for s in servos if s.body == "base")
        found[f"{leg}.thigh"], found[f"{leg}.calf"] = on_hip
    return found


class AnchorResolver:
    def __init__(self, instances: list[Instance], table: dict):
        self.instances = instances
        self.table = table
        self.servos = servo_instances(instances)

    def _vendor(self, vendor: str, match: str | None) -> Instance:
        hits = [
            i
            for i in self.instances
            if i.part == f"purchased/{vendor}" and (match is None or match in i.meta.get("label", ""))
        ]
        assert len(hits) == 1, f"{vendor} (match {match!r}): {len(hits)} placements"
        return hits[0]

    def resolve(self, name: str) -> Anchor:
        kind, _, key = name.partition(":")
        if kind == "servo":
            servo = self.servos[key]
            point, out = servo_lead_exit(servo)
            return Anchor(name, point, out, servo.body)
        if kind == "wago":
            side, bay, port, *rail = key.split(".")
            index = int(port.removeprefix("p"))
            points = []
            for name_rail in rail or ("V+", "GND"):
                wago = self._vendor("wago_221_415", f"WAGO 221-415 {side} {name_rail} {bay}")
                point, out = _world(wago, (WAGO_PORT_X[index], 0.0, WAGO_PORT_Z), (0, -1, 0))
                points.append(point)
            return Anchor(name, np.mean(points, axis=0), out, "base")
        if kind == "pca":
            channel = int(key)
            local = (PCA_CHANNEL_X0 + PCA_PITCH * (channel + channel // 4), PCA_PLUG_Y, PCA_PLUG_TOP_Z)
            point, out = _world(self._vendor("adafruit_pca9685", None), local, (0, 0, 1))
            return Anchor(name, point, out, "base")
        spec = self.table[name]
        if "vendor" in spec:
            point, out = _world(
                self._vendor(spec["vendor"], spec.get("match")), spec["local"], spec.get("out", (1, 0, 0))
            )
            return Anchor(name, point, _unit(spec["out_world"]) if "out_world" in spec else out, "base")
        return Anchor(name, np.asarray(spec["at"], dtype=float), _unit(spec["out"]), spec.get("body", "base"))
