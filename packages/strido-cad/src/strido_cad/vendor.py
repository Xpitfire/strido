"""Purchased components: official CAD when fetched, datasheet envelopes otherwise.

Every component is expressed in a documented *canonical frame* so the Strido
parts can be designed against it:

* official models are fetched by `strido_cad.fetch_vendor_cad` (`make vendor-cad`) into
  `build/vendor_cad/` (not committed: third-party licences) and re-framed here;
* envelopes are built with CadQuery from datasheet dimensions (committable,
  always available) and are used when the official file is absent.

All dimensions in millimetres. Sources: the docstring of each factory below and docs/bom/sources.md.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

import cadquery as cq
import manifold3d
import numpy as np
import trimesh
from scipy.spatial import QhullError

from .paths import CAD_CACHE

CACHE = CAD_CACHE / "step_cache"
OUT = CAD_CACHE / "vendor"


@dataclass
class VendorPart:
    id: str
    mesh: Path
    official: bool
    mass_g: float
    holes: list = field(default_factory=list)  # [(x, y, diameter)] in the canonical frame
    note: str = ""


def _cached_meshes(stem_fragment: str, keep=None) -> list[trimesh.Trimesh] | None:
    for manifest in sorted(CACHE.glob("*/manifest.json")):
        if stem_fragment in manifest.parent.name:
            meshes = []
            for entry in json.loads(manifest.read_text()):
                mesh = trimesh.load(entry["stl"])
                if keep is None or keep(mesh):
                    meshes.append(mesh)
            return meshes
    return None


def _solidify(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Union of all bodies as one closed manifold (vendor STEP files hold many touching solids).

    Bodies that are not closed (cosmetic surfaces) are replaced by their convex hull,
    which is conservative for clearance checks.
    """
    pieces = []
    for body in mesh.split(only_watertight=False):
        if len(body.faces) < 4 or body.area < 1e-3:
            continue  # degenerate fragments (lines, single faces)
        if not body.is_watertight:
            try:
                body = body.convex_hull
            except QhullError:  # flat fragments have no hull and carry no volume
                continue
        solid = manifold3d.Manifold(
            manifold3d.Mesh(
                vert_properties=np.asarray(body.vertices, dtype=np.float32),
                tri_verts=np.asarray(body.faces, dtype=np.uint32),
            )
        )
        if solid.status() != manifold3d.Error.NoError:
            hull = body.convex_hull
            solid = manifold3d.Manifold(
                manifold3d.Mesh(
                    vert_properties=np.asarray(hull.vertices, dtype=np.float32),
                    tri_verts=np.asarray(hull.faces, dtype=np.uint32),
                )
            )
        if solid.volume() > 1e-6:
            pieces.append(solid)
    merged = manifold3d.Manifold.batch_boolean(pieces, manifold3d.OpType.Add).to_mesh()
    return trimesh.Trimesh(np.asarray(merged.vert_properties)[:, :3], np.asarray(merged.tri_verts), process=False)


def _export(name: str, mesh: trimesh.Trimesh) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.stl"
    solid = _solidify(mesh)
    solid.export(path)
    return path


def _export_cq(name: str, shape: cq.Workplane) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.stl"
    cq.exporters.export(shape, str(path), tolerance=0.05, angularTolerance=0.2)
    return path


def _box(x0, y0, z0, x1, y1, z1) -> cq.Workplane:
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def _board(length, width, thickness, holes, hole_diameter) -> cq.Workplane:
    board = _box(0, 0, 0, length, width, thickness)
    for x, y in holes:
        board = board.cut(cq.Workplane("XY").circle(hole_diameter / 2).extrude(thickness).translate((x, y, 0)))
    return board


# ----------------------------------------------------------------------------- definitions
# Raspberry Pi 5: frame = board corner at the USB-C edge / non-port end, PCB bottom z=0,
# +x towards USB/Ethernet (85 mm), +y towards the 40-pin header (56 mm).
PI5_HOLES = [(3.5, 3.5, 2.7), (61.5, 3.5, 2.7), (3.5, 52.5, 2.7), (61.5, 52.5, 2.7)]  # measured in the official STEP


def raspberry_pi_5() -> VendorPart:
    meshes = _cached_meshes("rpi-5b_no_graphics")
    if meshes:
        mesh = trimesh.util.concatenate(meshes)
        official = True
    else:
        board = _board(85, 56, 1.4, [(x, y) for x, y, _ in PI5_HOLES], 2.7)
        ports = (
            _box(66.6, 2.5, 1.4, 87.9, 18.0, 14.5)  # Ethernet
            .union(_box(70.5, 21.8, 1.4, 88.0, 36.3, 17.5))  # USB stack
            .union(_box(70.3, 39.8, 1.4, 87.8, 54.3, 17.4))  # USB stack
            .union(_box(7.1, 50.0, 1.4, 57.9, 55.0, 10.0))  # 40-pin header incl. pins
        )
        mesh = trimesh.load(_export_cq("_pi5_tmp", board.union(ports)))
        official = False
    # Active Cooler envelope from the official drawing RP-008187: 63.5 x 42.5, 13.7 above the
    # PCB top, push pins in the Pi 5 cooler holes at (3.5, 9.5) and (61.5, 46.5); fin block on
    # the left, 30 x 30 blower top-right, open bottom-right corner over the CAM/DISP connectors.
    top = 1.31
    fins = _box(0.75, 6.75, top, 34.25, 49.25, top + 13.7)
    blower = _box(34.25, 19.25, top, 64.25, 49.25, top + 13.7)
    cooler = trimesh.load(_export_cq("_cooler_tmp", fins.union(blower)))
    return VendorPart(
        "raspberry_pi_5_with_active_cooler",
        _export("raspberry_pi_5", trimesh.util.concatenate([mesh, cooler])),
        official,
        46.0 + 27.0,
        PI5_HOLES,
        "Pi 5 official STEP + Active Cooler envelope",
    )


# Adafruit PCA9685 (815): frame = board corner, PCB bottom z=0; holes 55.88 x 19.05 pattern.
PCA_HOLES = [(3.175, 3.175, 2.5), (59.055, 3.175, 2.5), (3.175, 22.225, 2.5), (59.055, 22.225, 2.5)]


def pca9685() -> VendorPart:
    meshes = _cached_meshes("815 Servo Driver")
    if meshes:
        mesh = trimesh.util.concatenate(meshes)
        mesh.apply_translation((1.9, 6.48, 0.0))
        official = True
    else:
        shape = _board(62.23, 25.4, 1.6, [(x, y) for x, y, _ in PCA_HOLES], 2.5).union(
            _box(2.0, 1.0, 1.6, 60.0, 11.0, 10.1)
        )
        mesh = trimesh.load(_export_cq("_pca_tmp", shape))
        official = False
    return VendorPart("adafruit_pca9685", _export("adafruit_pca9685", mesh), official, 9.0, PCA_HOLES)


# Keep-out above the PCA9685 servo headers for the 12 plugged servo connectors
# (JR/Futaba housing 15.5 mm tall, 3 x 2.54 mm wide).
def pca9685_plug_keepout() -> Path:
    return _export_cq("pca9685_plug_keepout", _box(9.0, 1.0, 10.1, 60.0, 9.0, 10.1 + 15.5))


# Waveshare 2inch LCD: native frame of the official STEP (PCB centre origin,
# panel front face at z=+2.15, rear stand-offs end at z=-7.85).
LCD_HOLES = [(-28.215, 15.0, 2.2), (24.785, 15.0, 2.2), (-28.215, -15.0, 2.2), (24.785, -15.0, 2.2)]
LCD_PANEL = (-26.13, -17.3, 22.2, 17.3)  # x0, y0, x1, y1 of the glass
LCD_CONNECTOR = (14.53, -9.95, 23.04, 9.95)


def waveshare_lcd_2inch() -> VendorPart:
    meshes = _cached_meshes("2inch_LCD_Module")
    if meshes:
        mesh = trimesh.util.concatenate(meshes)
        official = True
    else:
        shape = (
            _box(-30.72, -17.5, -1.85, 27.29, 17.5, -0.25)
            .union(_box(LCD_PANEL[0], LCD_PANEL[1], -0.25, LCD_PANEL[2], LCD_PANEL[3], 2.15))
            .union(_box(LCD_CONNECTOR[0], LCD_CONNECTOR[1], -7.45, LCD_CONNECTOR[2], LCD_CONNECTOR[3], -1.85))
        )
        for x, y, _ in LCD_HOLES:
            shape = shape.union(cq.Workplane("XY").polygon(6, 3.5).extrude(6.0).translate((x, y, -7.85)))
        mesh = trimesh.load(_export_cq("_lcd_tmp", shape))
        official = False
    return VendorPart("waveshare_lcd_2inch", _export("waveshare_lcd_2inch", mesh), official, 14.0, LCD_HOLES)


# RPLIDAR C1: native frame (mount face z=0 at the centre, 4x M2.5 at (+-21.5, +-21.5),
# scan plane z=29.8, cable exits towards -x in the model).
LIDAR_HOLES = [(21.5, 21.5, 2.5), (-21.5, 21.5, 2.5), (21.5, -21.5, 2.5), (-21.5, -21.5, 2.5)]


def rplidar_c1() -> VendorPart:
    meshes = _cached_meshes("C1M1_appearance", keep=lambda m: m.bounds[0][0] > -28.5)
    if meshes:
        mesh = trimesh.util.concatenate(meshes)
        official = True
    else:
        shape = _box(-27.8, -27.8, 0, 27.8, 27.8, 23.1).union(
            cq.Workplane("XY").circle(27.3).extrude(18.2).translate((0, 0, 23.1))
        )
        mesh = trimesh.load(_export_cq("_lidar_tmp", shape))
        official = False
    return VendorPart("rplidar_c1", _export("rplidar_c1", mesh), official, 110.0, LIDAR_HOLES)


# Raspberry Pi Camera Module 3 Wide: native frame (PCB corner, lens towards -z).
CAMERA_HOLES = [(2.0, 2.0, 2.2), (14.5, 2.0, 2.2), (2.0, 23.0, 2.2), (14.5, 23.0, 2.2)]  # measured in the official STEP
CAMERA_LENS_CENTRE = (14.4, 12.5)  # lens axis = -z; FFC connector along the +x edge


def camera_module_3_wide() -> VendorPart:
    meshes = _cached_meshes("Camera_module_3_wide")
    if meshes:
        mesh = trimesh.util.concatenate(meshes)
        official = True
    else:
        shape = _board(23.86, 25.0, 1.0, [], 2.2).translate((0, 0, 1.6)).union(_box(7.4, 9.0, -8.8, 16.4, 18.0, 1.6))
        mesh = trimesh.load(_export_cq("_cam_tmp", shape))
        official = False
    return VendorPart(
        "rpi_camera_module_3_wide", _export("rpi_camera_module_3_wide", mesh), official, 4.0, CAMERA_HOLES
    )


# Pololu D36V50F5 5 V 5.5 A regulator: native frame (corner origin), three M2 mounting holes.
POLOLU_REG_HOLES = [
    (2.16, 2.16, 2.18),
    (23.24, 2.16, 2.18),
    (2.16, 23.24, 2.18),
]  # 3 mounting holes (measured, official STEP)


def pololu_d36v50f5() -> VendorPart:
    meshes = _cached_meshes("d36v50fx-step-down")
    if meshes:
        mesh = trimesh.util.concatenate(meshes)
        official = True
    else:
        mesh = trimesh.load(_export_cq("_reg_tmp", _box(0, 0, -6.1, 25.4, 25.4, 3.37)))
        official = False
    return VendorPart("pololu_d36v50f5", _export("pololu_d36v50f5", mesh), official, 7.0, POLOLU_REG_HOLES)


def pololu_power_switch_hp() -> VendorPart:
    meshes = _cached_meshes("big-pushbutton-power-switch")
    if meshes:
        mesh = trimesh.util.concatenate(meshes)
        official = True
    else:
        mesh = trimesh.load(_export_cq("_sw_tmp", _box(0, 0, 0, 20.32, 25.4, 3.96)))
        official = False
    # No mounting holes (the 4 large holes are power terminals): fixed with foam tape.
    holes = []
    return VendorPart("pololu_power_switch_hp", _export("pololu_power_switch_hp", mesh), official, 2.7, holes)


# Seeed XIAO ESP32S3 (pre-soldered): official STEP re-framed to PCB corner at the
# antenna end, PCB bottom z=0, +x towards USB-C, +y across (17.78), components +z.
# Male headers (2 x 7, 2.54 mm pitch, rows at y=1.27 / 16.51) point down (-z).
XIAO_PIN_ROWS_Y = (1.27, 16.51)
XIAO_PIN_X = tuple(2.86 + 2.54 * i for i in range(7))


def xiao_esp32s3() -> VendorPart:
    meshes = _cached_meshes("XIAO-ESP32S3")
    headers = _box(1.6, 0.0, -2.5, 19.4, 2.54, 0.0).union(_box(1.6, 15.24, -2.5, 19.4, 17.78, 0.0))
    for y in XIAO_PIN_ROWS_Y:
        for x in XIAO_PIN_X:
            headers = headers.union(_box(x - 0.32, y - 0.32, -8.5, x + 0.32, y + 0.32, -2.5))
    header_mesh = trimesh.load(_export_cq("_xiao_headers_tmp", headers))
    if meshes:
        board = trimesh.util.concatenate(meshes)
        frame = np.eye(4)
        frame[:3, :3] = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])
        frame[:3, 3] = (8.67, 2.78, 0.25)
        board.apply_transform(frame)
        official = True
    else:
        board = trimesh.load(
            _export_cq("_xiao_tmp", _box(0, 0, 0, 20.95, 17.78, 1.25).union(_box(13.6, 4.4, 1.25, 22.48, 13.4, 4.46)))
        )
        official = False
    return VendorPart(
        "seeed_xiao_esp32s3",
        _export("seeed_xiao_esp32s3", trimesh.util.concatenate([board, header_mesh])),
        official,
        3.0,
        [],
        "official STEP + modelled pre-soldered headers",
    )


def adafruit_lsm6dsox() -> VendorPart:
    holes = [(2.54, 15.24, 2.5), (22.86, 15.24, 2.5)]
    shape = _board(25.4, 17.78, 1.6, [(x, y) for x, y, _ in holes], 2.5).union(_box(9.0, 0.0, 1.6, 16.4, 4.0, 4.6))
    return VendorPart(
        "adafruit_lsm6dsox", _export_cq("adafruit_lsm6dsox", shape), False, 1.7, holes, "outline from Eagle .brd"
    )


def adafruit_ina260() -> VendorPart:
    holes = [(2.54, 20.32, 2.5), (20.32, 20.32, 2.5)]
    shape = _board(22.86, 22.86, 1.6, [(x, y) for x, y, _ in holes], 2.5).union(_box(5.3, 14.0, 1.6, 17.6, 22.0, 11.6))
    return VendorPart(
        "adafruit_ina260", _export_cq("adafruit_ina260", shape), False, 2.0, holes, "outline from Eagle .brd"
    )


def battery_2s_5000() -> VendorPart:
    shape = _box(0, 0, 0, 138, 47, 25).edges("|X").fillet(3.0)
    return VendorPart(
        "lipo_2s_5000_gensace", _export_cq("lipo_2s_5000", shape), False, 250.0, [], "Gens ace GEA502S60X6HGT 138x47x25"
    )


def wago_221_415() -> VendorPart:
    shape = _box(0, 0, 0, 30.0, 18.8, 8.4)
    return VendorPart(
        "wago_221_415", _export_cq("wago_221_415", shape), False, 4.0, [], "WAGO datasheet 30 x 8.4 x 18.8"
    )


def hobbywing_ubec_10a() -> VendorPart:
    # Hobbywing UBEC-10A (car, IP67, metal case): 45 x 20 x 16.2 mm, 34 g with leads (user guide 20201221).
    shape = _box(0, 0, 0, 45.0, 20.0, 16.2)
    return VendorPart(
        "hobbywing_ubec_10a",
        _export_cq("hobbywing_ubec_10a", shape),
        False,
        34.0,
        [],
        "Hobbywing UBEC-10A user guide 45 x 20 x 16.2",
    )


def fuse_holder() -> VendorPart:
    meshes = _cached_meshes("OL-FHAC0001ZXJ")
    if meshes:
        mesh = trimesh.util.concatenate(meshes)
        # keep the body only (leads are flexible wires, routed separately)
        mesh = mesh.slice_plane([-26, 0, 0], [1, 0, 0]).slice_plane([26, 0, 0], [-1, 0, 0])
        official = True
    else:
        mesh = trimesh.load(_export_cq("_fuse_tmp", _box(-25, -16.1, -3.8, 25, 16.1, 12.0)))
        official = False
    return VendorPart("fuse_holder_ato", _export("fuse_holder_ato", mesh), official, 12.0)


def pushbutton_12mm() -> VendorPart:
    # ONPOW GQ12B-10J class: D12 cutout, 27.5 mm behind the panel; frame: panel outer face z=0,
    # bezel outside (z<0), threaded body through a 2 mm panel and 27.5 mm deep inside.
    shape = cylinder_z(5.95, 0.0, 29.5).union(cylinder_z(7.0, -2.0, 0.0))
    return VendorPart(
        "pushbutton_12mm", _export_cq("pushbutton_12mm", shape), False, 6.0, [], "GQ12 class momentary, D12 cutout"
    )


def xt60h_female() -> VendorPart:
    # AMASS XT60H-F: hood 16.4 x 9.2, length 23.5 incl. hood; frame: hood face at z=0, body towards +z.
    shape = _box(-8.2, -4.6, 0.0, 8.2, 4.6, 23.5)
    return VendorPart("xt60h_female", _export_cq("xt60h_female", shape), False, 4.0, [], "AMASS XT60H-F envelope")


def cable_tie_mount() -> VendorPart:
    # HellermannTyton MB2APT-A class adhesive cable-tie mount: 13 x 13 x 4.1 mm; frame: adhesive base on z=0, centred.
    shape = _box(-6.5, -6.5, 0.0, 6.5, 6.5, 4.1)
    return VendorPart("cable_tie_mount", _export_cq("cable_tie_mount", shape), False, 1.0, [], "MB2APT-A envelope")


def cylinder_z(radius, z0, z1) -> cq.Workplane:
    return cq.Workplane("XY").circle(radius).extrude(z1 - z0).translate((0, 0, z0))


def lidar_usb_adapter() -> VendorPart:
    # Slamtec C1 dev-kit adapter board: no published drawing -> generous envelope (UNVERIFIED size).
    return VendorPart(
        "rplidar_usb_adapter",
        _export_cq("rplidar_usb_adapter", _box(0, 0, 0, 32, 22, 10)),
        False,
        6.0,
        [],
        "envelope only, secure with foam tape in the tray pocket",
    )


ALL = (
    raspberry_pi_5,
    pca9685,
    waveshare_lcd_2inch,
    rplidar_c1,
    camera_module_3_wide,
    pololu_d36v50f5,
    pololu_power_switch_hp,
    xiao_esp32s3,
    adafruit_lsm6dsox,
    adafruit_ina260,
    battery_2s_5000,
    wago_221_415,
    fuse_holder,
    lidar_usb_adapter,
    pushbutton_12mm,
    xt60h_female,
    hobbywing_ubec_10a,
    cable_tie_mount,
)


def build_all() -> dict[str, VendorPart]:
    parts = {}
    for factory in ALL:
        part = factory()
        parts[part.id] = part
    pca9685_plug_keepout()
    return parts


if __name__ == "__main__":
    for part in build_all().values():
        mesh = trimesh.load(part.mesh)
        print(f"{part.id:36s} official={part.official!s:5s} bounds={np.round(mesh.bounds, 2).tolist()}")
