"""Strido additions to the upstream Yertle mechanics (all coordinates: upstream STEP frame, mm).

STEP frame recap: +x = robot left, +y = robot rear, +z = up. Key upstream surfaces
(measured by ray casting the placed upstream STLs, see docs/design.md):

* front shell face: outer y=-165.7, inner y=-164.2, flat x -59..49, z 35..101
* top shell: outer z=106.5, inner z=104.5; full width y -69..91, end tabs x -30..20
* back shell face: outer y=205.85, inner y=203.85; holes D11.5 @ (x-5, z81.5) and D20 @ (x-5, z51.5)
* electronics plate: top z=67.5; 5 mm thick at the sides, 3 mm in the centre (x -30..20)
* lower shoulder frames: top z~46.2; front y -139.5..-69.1, rear y 90.5..160.9, x -15.7..5.6
* inner/outer shoulder frames: central opening x -25..15, z ~47..93

Modified upstream parts keep the upstream STL print orientation; new parts declare
which face goes on the bed. Every fastener is placed explicitly so the BOM, the
assembly manual and the interference check all use the same list.
"""

import math
from dataclasses import dataclass, field

import numpy as np
import trimesh

from . import assembly, vendor
from .geom import boolean, box, cylinder, rotation, to_mesh, translation

# --------------------------------------------------------------------------- data types


@dataclass
class Fastener:
    spec: str  # key in hardware/fasteners.yaml
    head: tuple  # world point on the bearing face (under the head / nut face)
    axis: tuple  # unit vector pointing from the head into the joint
    body: str = "base"
    joint: str = ""


@dataclass
class NewPart:
    part: str
    title: str
    mesh: trimesh.Trimesh
    body: str = "base"
    print_down: tuple | None = None  # world direction placed on the bed; None = keep upstream orientation
    replaces: str | None = None
    material: str = "PETG"
    infill_percent: int = 25
    supports: bool = False
    note: str = ""


@dataclass
class VendorPlacement:
    vendor_id: str
    matrix: np.ndarray
    body: str = "base"
    label: str = ""


@dataclass
class Module:
    name: str
    parts: list = field(default_factory=list)
    vendors: list = field(default_factory=list)
    fasteners: list = field(default_factory=list)


# --------------------------------------------------------------------------- constants
FRONT_INNER_Y = -164.2
TOP_OUTER_Z = 106.5
TOP_INNER_Z = 104.5
BACK_INNER_Y = 203.85
BACK_OUTER_Y = 205.85
PLATE_TOP_Z = 67.5
LOWER_SHOULDER_TOP_Z = 46.55  # crown of the lower shoulder frame (46.5) + 0.05 seat clearance
PI_STANDOFF_MM = 6.0

LCD_ORIGIN = np.array([-3.035, FRONT_INNER_Y + 2.15, 72.0])  # panel front touches the inner face
LCD_ROTATION = rotation([(1, 0, 0), (0, 0, 1), (0, -1, 0)])  # module x->X, y->Z, z->-Y
DISPLAY_BOSS_X = (-40.5, 31.5)
DISPLAY_BOSS_LENGTH = 10.0  # inner face -> rear stud plane of the LCD (Waveshare drawing: 10.00)

LIDAR_CENTRE = np.array([-5.0, 55.0])  # pedestal / sensor centre on the top shell
PEDESTAL_HEIGHT = 14.0  # cavity holds the LiDAR USB adapter (envelope 32 x 22 x 10)
PEDESTAL_HALF = 28.0
PEDESTAL_PILOT_DEPTH = 11.0  # screw tip at 10.0 mm into the pedestal; column top at 11.0 (3 mm top plate kept)
PEDESTAL_SCREWS = ((-23.0, 0.0), (23.0, 0.0), (-14.0, 23.0), (14.0, 23.0))  # relative to LIDAR_CENTRE (x, y)
LIDAR_ROTATION = rotation([(0, 1, 0), (-1, 0, 0), (0, 0, 1)])  # model -x (cable) -> robot front (STEP -y)

CAMERA_PIVOT = np.array([0.0, -136.0, 120.0])  # on the front shell top; x unused, pivot axis along STEP x
CAMERA_LENS_Z = 127.5  # lens centre height (pivot sits below the lower camera screws)
CAMERA_TILT_DEG = 15.0  # nominal downward tilt
CAMERA_PLATE_X = (-19.8, 9.8)
CAMERA_CHEEK_X = ((-23.0, -20.0), (10.0, 13.0))
CAMERA_BASE_Y = (-144.0, -116.0)  # flat part of the front shell top (slope starts at y=-144)
CAMERA_SCREWS = ((-20.0, -120.4), (10.0, -120.4))  # shared with the upstream front-shell screws (nut pockets)
CAMERA_FFC_SLOT = (-14.0, -150.0, 4.0, -146.5)  # x0, y0, x1, y1 through the sloped shell nose


def upstream_world(part: str, select=None) -> trimesh.Trimesh:
    matches = [item for item in assembly.upstream_instances() if item.part == part]
    if select is not None:
        matches = [item for item in matches if select(assembly.world_mesh(item))]
    assert len(matches) == 1, f"{part}: {len(matches)} matches"
    return assembly.world_mesh(matches[0])


# --------------------------------------------------------------------------- front: display
def front_display_module() -> Module:
    module = Module("front display")
    shell = upstream_world("printed/front_shell")
    window = box(-26.5, -168.0, 55.5, 16.5, -163.0, 88.5).edges("|Y").fillet(1.5)
    bosses = []
    pilots = []
    for x in DISPLAY_BOSS_X:
        bosses.append(cylinder((x, 0, 72.0), (0, 1, 0), 4.0, FRONT_INNER_Y - 0.5, FRONT_INNER_Y + DISPLAY_BOSS_LENGTH))
        pilots.append(
            cylinder((x, 0, 72.0), (0, 1, 0), 1.3, FRONT_INNER_Y + 2.0, FRONT_INNER_Y + DISPLAY_BOSS_LENGTH + 0.1)
        )
    sx0, sy0, sx1, sy1 = CAMERA_FFC_SLOT
    ffc_slot = box(sx0, sy0, 95.0, sx1, sy1, 112.0)  # camera ribbon into the front shell
    front = boolean(shell, add=bosses, cut=[window, *pilots, ffc_slot])
    module.parts.append(
        NewPart(
            "printed/front_shell_display",
            "Front shell with display window",
            front,
            print_down=(0, -1, 0),
            replaces="printed/front_shell",
            note="upstream Front_Shell + 43x33 display window, 2 display bosses, camera ribbon slot",
        )
    )

    bracket_y0 = FRONT_INNER_Y + DISPLAY_BOSS_LENGTH
    bracket = box(-46.0, bracket_y0, 52.0, 37.0, bracket_y0 + 3.0, 92.0).edges("|Y").fillet(3.0)
    cuts = [box(10.0, bracket_y0 - 1, 59.0, 21.5, bracket_y0 + 4, 85.0)]  # LCD connector + cable
    lcd_world = LCD_ROTATION.copy()
    lcd_world[:3, 3] = LCD_ORIGIN
    stud_points = []
    for hole_x, hole_y, _ in vendor.LCD_HOLES:
        point = (lcd_world @ np.array([hole_x, hole_y, -7.85, 1.0]))[:3]
        stud_points.append(point)
        cuts.append(cylinder(point, (0, 1, 0), 1.2, -1, 5))
    for x in DISPLAY_BOSS_X:
        cuts.append(cylinder((x, 0, 72.0), (0, 1, 0), 1.7, bracket_y0 - 1, bracket_y0 + 4))
    bracket_mesh = boolean(to_mesh(bracket), cut=cuts)
    module.parts.append(NewPart("printed/display_bracket", "Display bracket", bracket_mesh, print_down=(0, 1, 0)))
    module.vendors.append(VendorPlacement("waveshare_lcd_2inch", lcd_world, label='2" IPS LCD (ST7789V)'))
    for point in stud_points:
        module.fasteners.append(
            Fastener(
                "iso4762_m2x5", (point[0], bracket_y0 + 3.0, point[2]), (0, -1, 0), joint="bracket -> LCD hex studs"
            )
        )
    for x in DISPLAY_BOSS_X:
        module.fasteners.append(
            Fastener(
                "iso4762_m3x10",
                (x, bracket_y0 + 3.0, 72.0),
                (0, -1, 0),
                joint="bracket -> front shell boss (self-tapping)",
            )
        )
    return module


# --------------------------------------------------------------------------- top: LiDAR + camera
def _pedestal_mesh():
    cx, cy = LIDAR_CENTRE
    z0, z1 = TOP_OUTER_Z, TOP_OUTER_Z + PEDESTAL_HEIGHT
    outer = (
        box(cx - PEDESTAL_HALF, cy - PEDESTAL_HALF, z0, cx + PEDESTAL_HALF, cy + PEDESTAL_HALF, z1)
        .edges("|Z")
        .fillet(4.0)
    )
    inner = box(cx - 25.0, cy - 25.0, z0 - 1, cx + 25.0, cy + 25.0, z1 - 3.0)
    shape = outer.cut(inner)
    for dx, dy in PEDESTAL_SCREWS:  # screw columns inside the walls
        column = box(cx + dx - 4.5, cy + dy - 4.5, z0, cx + dx + 4.5, cy + dy + 4.5, z1 - 3.0)
        shape = shape.union(column.intersect(outer))
    cuts = []
    for dx, dy in PEDESTAL_SCREWS:  # M3x12 from below through the 2 mm shell: 10 mm protrusion + 1 mm pilot reserve
        cuts.append(cylinder((cx + dx, cy + dy, z0), (0, 0, 1), 1.3, -0.1, PEDESTAL_PILOT_DEPTH))
    for hx, hy, _ in vendor.LIDAR_HOLES:  # sensor holes after the 90 deg mounting rotation
        world = LIDAR_ROTATION[:3, :3] @ np.array([hx, hy, 0.0])
        cuts.append(cylinder((cx + world[0], cy + world[1], z1), (0, 0, 1), 1.4, -3.5, 0.5))
    cuts.append(box(cx - 7.0, cy - 28.5, z1 - 4.0, cx + 7.0, cy - 19.0, z1 + 1.0))  # cable notch (sensor front)
    return boolean(to_mesh(shape), cut=cuts)


def _camera_base_mesh():
    y0, y1 = CAMERA_BASE_Y
    base = box(-25.0, y0, TOP_OUTER_Z, 15.0, y1, TOP_OUTER_Z + 3.0).edges("|Z").fillet(2.0)
    shape = base
    for x0, x1 in CAMERA_CHEEK_X:
        cheek = box(x0, CAMERA_PIVOT[1] - 8.0, TOP_OUTER_Z, x1, CAMERA_PIVOT[1] + 8.0, CAMERA_PIVOT[2])
        cap = cylinder((x0, CAMERA_PIVOT[1], CAMERA_PIVOT[2]), (1, 0, 0), 6.0, 0, x1 - x0)
        shape = shape.union(cheek).union(cap)
    cuts = [cylinder((0, CAMERA_PIVOT[1], CAMERA_PIVOT[2]), (1, 0, 0), 1.7, -30, 20)]
    for x, y in CAMERA_SCREWS:
        cuts.append(cylinder((x, y, TOP_OUTER_Z), (0, 0, 1), 1.7, -1, 4))
    return boolean(to_mesh(shape), cut=cuts)


CAMERA_PCB_BACK_Y = CAMERA_PIVOT[1] - 5.5 - 3.0  # tilt plate front face minus 3 mm bosses


def camera_world_matrix(tilt_deg: float) -> np.ndarray:
    """Camera Module 3 canonical frame -> STEP world for a downward tilt (degrees)."""
    rotate = rotation([(0, 0, -1), (-1, 0, 0), (0, 1, 0)])  # cam x->-Z (FFC edge down), y->-X, z(back)->+Y
    lens = rotate[:3, :3] @ np.array([*vendor.CAMERA_LENS_CENTRE, 0.0])
    target = np.array([-5.0, CAMERA_PCB_BACK_Y, CAMERA_LENS_Z])  # lens on the robot mid-plane
    placed = translation(target - lens) @ rotate
    tilt = trimesh.transformations.rotation_matrix(
        math.radians(tilt_deg), (1, 0, 0), (0, CAMERA_PIVOT[1], CAMERA_PIVOT[2])
    )
    return tilt @ placed


def _camera_plate_mesh(tilt_deg: float):
    y_front = CAMERA_PIVOT[1] - 5.5
    plate = box(
        CAMERA_PLATE_X[0], y_front, CAMERA_PIVOT[2] - 5.0, CAMERA_PLATE_X[1], y_front + 3.0, CAMERA_LENS_Z + 15.0
    )
    axle = cylinder(
        (CAMERA_PLATE_X[0], CAMERA_PIVOT[1], CAMERA_PIVOT[2]), (1, 0, 0), 5.0, 0, CAMERA_PLATE_X[1] - CAMERA_PLATE_X[0]
    )
    web = box(
        CAMERA_PLATE_X[0], y_front, CAMERA_PIVOT[2] - 5.0, CAMERA_PLATE_X[1], CAMERA_PIVOT[1], CAMERA_PIVOT[2] + 5.0
    )
    shape = plate.union(axle).union(web)
    cam = camera_world_matrix(0.0)
    bosses, cuts = [], [cylinder((0, CAMERA_PIVOT[1], CAMERA_PIVOT[2]), (1, 0, 0), 1.7, -30, 20)]
    for hx, hy, _ in vendor.CAMERA_HOLES:
        point = (cam @ np.array([hx, hy, 0.0, 1.0]))[:3]
        bosses.append(cylinder(point, (0, 1, 0), 2.2, 0.0, y_front - point[1] + 0.5))
        cuts.append(cylinder(point, (0, 1, 0), 1.1, -1.0, 12.0))
    mesh = boolean(to_mesh(shape), add=bosses, cut=cuts)
    tilt = trimesh.transformations.rotation_matrix(
        math.radians(tilt_deg), (1, 0, 0), (0, CAMERA_PIVOT[1], CAMERA_PIVOT[2])
    )
    mesh.apply_transform(tilt)
    return mesh


def camera_module() -> Module:
    """Camera Module 3 Wide on a friction tilt hinge at the front of the front shell (MP4 style)."""
    module = Module("front camera")
    module.parts.append(
        NewPart(
            "printed/camera_mount_base",
            "Camera mount base",
            _camera_base_mesh(),
            print_down=(0, 0, -1),
            note="print standing on its base; the M3 pivot bore prints horizontal (a 3.4 mm drill clears it if tight)",
        )
    )
    module.parts.append(
        NewPart(
            "printed/camera_tilt_plate", "Camera tilt plate", _camera_plate_mesh(CAMERA_TILT_DEG), print_down=(0, 1, 0)
        )
    )
    module.vendors.append(
        VendorPlacement("rpi_camera_module_3_wide", camera_world_matrix(CAMERA_TILT_DEG), label="Camera Module 3 Wide")
    )
    for x, y in CAMERA_SCREWS:
        module.fasteners.append(
            Fastener(
                "iso4762_m3x12",
                (x, y, TOP_OUTER_Z + 3.0),
                (0, 0, -1),
                joint="camera base + front shell -> upper shoulder frame nut (replaces upstream M3x8)",
            )
        )
        module.fasteners.append(
            Fastener(
                "iso4032_m3", (x, y, 101.5), (0, 0, -1), joint="captive nut in upper shoulder frame (upstream pocket)"
            )
        )
    module.fasteners.append(
        Fastener(
            "iso4762_m3x40",
            (CAMERA_CHEEK_X[1][1], CAMERA_PIVOT[1], CAMERA_PIVOT[2]),
            (-1, 0, 0),
            joint="camera tilt pivot",
        )
    )
    module.fasteners.append(
        Fastener(
            "din985_m3",
            (CAMERA_CHEEK_X[0][0], CAMERA_PIVOT[1], CAMERA_PIVOT[2]),
            (-1, 0, 0),
            joint="pivot nyloc (friction)",
        )
    )
    cam = camera_world_matrix(CAMERA_TILT_DEG)
    plate_back = (CAMERA_PIVOT[1] - 5.5 + 3.0) - CAMERA_PCB_BACK_Y
    for hx, hy, _ in vendor.CAMERA_HOLES:
        front = (cam @ np.array([hx, hy, -0.7, 1.0]))[:3]
        module.fasteners.append(
            Fastener("iso4762_m2x10", tuple(front), tuple(cam[:3, 2]), joint="camera PCB -> tilt plate bosses")
        )
        back = (cam @ np.array([hx, hy, plate_back, 1.0]))[:3]
        module.fasteners.append(
            Fastener("iso4032_m2", tuple(back), tuple(cam[:3, 2]), joint="M2 nut behind tilt plate")
        )
    return module


def top_sensor_module() -> Module:
    module = Module("top sensors")
    shell = upstream_world("printed/top_shell")
    cx, cy = LIDAR_CENTRE
    cuts = [cylinder((cx + dx, cy + dy, TOP_INNER_Z), (0, 0, 1), 1.7, -1, 3) for dx, dy in PEDESTAL_SCREWS]
    cuts.append(box(cx - 7.0, cy - 22.0, TOP_INNER_Z - 1, cx + 7.0, cy - 12.0, TOP_OUTER_Z + 1))  # LiDAR cable slot
    top = boolean(shell, cut=cuts)
    module.parts.append(
        NewPart(
            "printed/top_shell_sensor",
            "Top shell with sensor mounts",
            top,
            replaces="printed/top_shell",
            print_down=(0, 0, 1),
            note="upstream Top_Shell + LiDAR pedestal holes and LiDAR USB cable slot",
        )
    )
    module.parts.append(
        NewPart(
            "printed/lidar_pedestal",
            "LiDAR pedestal",
            _pedestal_mesh(),
            print_down=(0, 0, 1),
            note="print upside down (top plate on the bed)",
        )
    )
    lidar = LIDAR_ROTATION.copy()
    lidar[:3, 3] = (cx, cy, TOP_OUTER_Z + PEDESTAL_HEIGHT)
    module.vendors.append(VendorPlacement("rplidar_c1", lidar, label="Slamtec RPLIDAR C1"))
    # inside the pedestal between the slot and the rear screw columns, USB end (local +x) towards the slot (-Y)
    adapter = translation((cx - 11.0, cy + 18.0, TOP_OUTER_Z)) @ rotation([(0, -1, 0), (1, 0, 0), (0, 0, 1)])
    module.vendors.append(
        VendorPlacement("rplidar_usb_adapter", adapter, label="RPLIDAR USB adapter (foam tape, inside the pedestal)")
    )

    for hx, hy, _ in vendor.LIDAR_HOLES:
        world = LIDAR_ROTATION[:3, :3] @ np.array([hx, hy, 0.0])
        z_under = TOP_OUTER_Z + PEDESTAL_HEIGHT - 3.0
        module.fasteners.append(
            Fastener("iso4762_m2_5x6", (cx + world[0], cy + world[1], z_under), (0, 0, 1), joint="LiDAR -> pedestal")
        )
    for dx, dy in PEDESTAL_SCREWS:
        module.fasteners.append(
            Fastener(
                "iso4762_m3x12",
                (cx + dx, cy + dy, TOP_INNER_Z),
                (0, 0, 1),
                joint="pedestal -> top shell (from below, self-tapping)",
            )
        )
    return module


# --------------------------------------------------------------------------- rear: power button + servo arming port
BUTTON_CENTRE = (-5.0, 81.5)  # (x, z) upstream D11.5 hole, enlarged to D12.2 for a 12 mm momentary button
ARMING_CENTRE = (-5.0, 51.5)  # (x, z) upstream D20 hole -> XT60 arming port bezel
XT60_WINDOW = (16.6, 9.4)  # AMASS XT60H hood 16.4 x 9.2 + clearance
XT60_CORNER_RELIEF = 0.5  # dog-bone radius at the XT60 window corners; keeps 0.96 mm of the 11 mm clamp ring


def back_module() -> Module:
    module = Module("rear panel")
    shell = upstream_world("printed/back_shell")
    bx, bz = BUTTON_CENTRE
    back = boolean(shell, cut=[cylinder((bx, 0, bz), (0, 1, 0), 6.1, BACK_INNER_Y - 1, BACK_OUTER_Y + 1)])
    module.parts.append(
        NewPart(
            "printed/back_shell_button",
            "Back shell with power button hole",
            back,
            print_down=(0, 1, 0),
            replaces="printed/back_shell",
            note="upstream Back_Shell with the D11.5 hole opened to D12.2",
        )
    )

    ax, az = ARMING_CENTRE
    wx, wz = XT60_WINDOW

    def xt60_window(y0: float, y1: float) -> list:
        """Rectangular XT60 window with dog-bone corner reliefs: FDM rounds inner corners by about the
        nozzle radius, so the square hood would bind without them."""
        corners = [(ax + sx * wx / 2, az + sz * wz / 2) for sx in (-1, 1) for sz in (-1, 1)]
        reliefs = [cylinder((cx, 0, cz), (0, 1, 0), XT60_CORNER_RELIEF, y0, y1) for cx, cz in corners]
        return [box(ax - wx / 2, y0, az - wz / 2, ax + wx / 2, y1, az + wz / 2), *reliefs]

    flange = cylinder((ax, 0, az), (0, 1, 0), 13.0, BACK_OUTER_Y, BACK_OUTER_Y + 2.5)
    boss = cylinder((ax, 0, az), (0, 1, 0), 9.8, BACK_INNER_Y, BACK_OUTER_Y + 0.1)
    # The window diagonal (19.1 mm) nearly equals the 19.6 mm boss that centres the bezel in the D20 hole:
    # instead of 0.3 mm slivers at the corners, the boss keeps only an upper and a lower arc.
    band = XT60_WINDOW[1] / 2 + XT60_CORNER_RELIEF
    boss_split = box(ax - 11.0, BACK_INNER_Y - 1.0, az - band, ax + 11.0, BACK_OUTER_Y, az + band)
    pilots = [cylinder((ax, 0, az + dz), (0, 1, 0), 1.05, BACK_INNER_Y - 0.1, BACK_OUTER_Y + 1.5) for dz in (-7.2, 7.2)]
    bezel = boolean(
        to_mesh(flange.union(boss)), cut=[*xt60_window(BACK_INNER_Y - 5, BACK_OUTER_Y + 5), boss_split, *pilots]
    )
    module.parts.append(
        NewPart("printed/arming_port_bezel", "Servo arming port bezel (outside)", bezel, print_down=(0, 1, 0))
    )
    ring = cylinder(
        (ax, 0, az), (0, 1, 0), 11.0, BACK_INNER_Y - 3.0, BACK_INNER_Y
    )  # clears the thicker wall below z=40
    ring_cuts = xt60_window(BACK_INNER_Y - 5, BACK_INNER_Y + 1)
    ring_cuts += [cylinder((ax, 0, az + dz), (0, 1, 0), 1.4, BACK_INNER_Y - 4, BACK_INNER_Y + 1) for dz in (-7.2, 7.2)]
    module.parts.append(
        NewPart(
            "printed/arming_port_ring",
            "Servo arming port clamp ring (inside)",
            boolean(to_mesh(ring), cut=ring_cuts),
            print_down=(0, -1, 0),
        )
    )
    for dz in (-7.2, 7.2):
        module.fasteners.append(
            Fastener(
                "iso4762_m2_5x6",
                (ax, BACK_INNER_Y - 3.0, az + dz),
                (0, 1, 0),
                joint="clamp ring -> bezel through the D20 hole",
            )
        )
    inward = rotation([(1, 0, 0), (0, 0, 1), (0, -1, 0)])  # local +z -> -Y (into the robot)
    module.vendors.append(
        VendorPlacement("pushbutton_12mm", translation((bx, BACK_OUTER_Y, bz)) @ inward, label="12 mm power pushbutton")
    )
    module.vendors.append(
        VendorPlacement(
            "xt60h_female", translation((ax, BACK_OUTER_Y + 2.5, az)) @ inward, label="XT60H-F servo arming jack"
        )
    )
    return module


# --------------------------------------------------------------------------- deck: compute + IMU + servo bus
PI_ROTATION = rotation([(0, -1, 0), (1, 0, 0), (0, 0, 1)])  # Pi x -> -Y (ports to the front), Pi y -> +X
PI_ORIGIN = np.array([-33.0, 26.5, PLATE_TOP_Z + PI_STANDOFF_MM])
PCA_ORIGIN = np.array([-33.2 - 3.175, 31.8 - 3.175, PLATE_TOP_Z + PI_STANDOFF_MM])  # upstream PCA holes
IMU_POCKET = (-22.0, -30.0, 3.4, -12.22)  # x0, y0, x1, y1 under the Pi, 1.5 mm deep
IMU_BOARD_ORIGIN = np.array([-22.0 + 0.0, -30.0 + 0.0, PLATE_TOP_Z - 1.5])
POWER_ZONE = {"regulator": (-29.0, 57.0), "ina260": (-2.5, 58.0)}  # board corners (x, y) on the deck rear zone
REGULATOR_STANDOFF = 8.0  # M2 x 8 stand-offs: the D36V50F5 has parts 6.1 mm below its PCB


def deck_module() -> Module:
    module = Module("electronics deck")
    plate = upstream_world("printed/electronics_mounting_plate")
    x0, y0, x1, y1 = IMU_POCKET
    cuts = [box(x0 - 0.3, y0 - 0.3, PLATE_TOP_Z - 1.5, x1 + 0.3, y1 + 0.3, PLATE_TOP_Z + 1)]
    imu_holes = [(x0 + hx, y0 + hy) for hx, hy, _ in vendor.adafruit_lsm6dsox().holes]
    cuts += [cylinder((x, y, 0), (0, 0, 1), 1.4, 60, 70) for x, y in imu_holes]
    rx, ry = POWER_ZONE["regulator"]
    for hx, hy, _ in vendor.POLOLU_REG_HOLES:  # M2 clearance for the stand-off screws
        cuts.append(cylinder((rx + hx, ry + hy, 0), (0, 0, 1), 1.15, 60, 70))
    ix, iy = POWER_ZONE["ina260"]
    for hx, hy, _ in vendor.adafruit_ina260().holes:  # M2.5 clearance
        cuts.append(cylinder((ix + hx, iy + hy, 0), (0, 0, 1), 1.4, 60, 70))
    deck = boolean(plate, cut=cuts)
    module.parts.append(
        NewPart(
            "printed/electronics_deck",
            "Electronics deck",
            deck,
            replaces="printed/electronics_mounting_plate",
            print_down=(0, 0, 1),
            supports=True,
            note="upstream plate + IMU pocket and stand-off holes for the regulator and INA260; print top face down "
            "with supports (the IMU pocket floor is an 18 mm bridge the slicer flags without them)",
        )
    )
    pi = translation(PI_ORIGIN) @ PI_ROTATION
    module.vendors.append(VendorPlacement("raspberry_pi_5", pi, label="Raspberry Pi 5 + Active Cooler"))
    module.vendors.append(VendorPlacement("adafruit_pca9685", translation(PCA_ORIGIN), label="PCA9685 servo driver"))
    module.vendors.append(
        VendorPlacement("pca9685_plug_keepout", translation(PCA_ORIGIN), label="servo plugs (keep-out)")
    )
    module.vendors.append(VendorPlacement("adafruit_lsm6dsox", translation(IMU_BOARD_ORIGIN), label="LSM6DSOX IMU"))
    module.vendors.append(
        VendorPlacement(
            "pololu_d36v50f5", translation((rx, ry, PLATE_TOP_Z + REGULATOR_STANDOFF)), label="5 V 5.5 A regulator"
        )
    )
    module.vendors.append(
        VendorPlacement(
            "adafruit_ina260", translation((ix, iy, PLATE_TOP_Z + PI_STANDOFF_MM)), label="INA260 power monitor"
        )
    )
    pi_holes = [(-29.5, -35.0), (19.5, -35.0), (-29.5, 23.0), (19.5, 23.0)]
    pca_holes = [(-33.2, 31.8), (22.8, 31.8), (-33.2, 50.8), (22.8, 50.8)]
    for x, y in pi_holes + pca_holes:
        module.fasteners.append(Fastener("standoff_m2_5_ff_6", (x, y, PLATE_TOP_Z), (0, 0, 1), joint="board stand-off"))
        module.fasteners.append(
            Fastener("iso4762_m2_5x5", (x, y, 65.0), (0, 0, 1), joint="stand-off -> deck (from below, head in pocket)")
        )
        module.fasteners.append(
            Fastener(
                "iso4762_m2_5x5", (x, y, PLATE_TOP_Z + PI_STANDOFF_MM + 1.6), (0, 0, -1), joint="board -> stand-off"
            )
        )
    for x, y in imu_holes:
        module.fasteners.append(
            Fastener("iso4762_m2_5x6", (x, y, PLATE_TOP_Z - 1.5 + 1.6), (0, 0, -1), joint="IMU -> deck")
        )
        module.fasteners.append(
            Fastener("iso4032_m2_5", (x, y, PLATE_TOP_Z - 3.0), (0, 0, -1), joint="IMU nut under the deck")
        )
    for hx, hy, _ in vendor.POLOLU_REG_HOLES:
        x, y = rx + hx, ry + hy
        module.fasteners.append(
            Fastener("standoff_m2_ff_8", (x, y, PLATE_TOP_Z), (0, 0, 1), joint="regulator stand-off")
        )
        module.fasteners.append(
            Fastener(
                "iso4762_m2x5",
                (x, y, PLATE_TOP_Z + REGULATOR_STANDOFF + 1.6),
                (0, 0, -1),
                joint="regulator -> stand-off",
            )
        )
        module.fasteners.append(
            Fastener("iso4762_m2x5", (x, y, PLATE_TOP_Z - 3.0), (0, 0, 1), joint="stand-off -> deck (from below)")
        )
    for hx, hy, _ in vendor.adafruit_ina260().holes:
        x, y = ix + hx, iy + hy
        module.fasteners.append(
            Fastener("standoff_m2_5_ff_6", (x, y, PLATE_TOP_Z), (0, 0, 1), joint="INA260 stand-off")
        )
        module.fasteners.append(
            Fastener(
                "iso4762_m2_5x5", (x, y, PLATE_TOP_Z + PI_STANDOFF_MM + 1.6), (0, 0, -1), joint="INA260 -> stand-off"
            )
        )
        module.fasteners.append(
            Fastener("iso4762_m2_5x5", (x, y, PLATE_TOP_Z - 3.0), (0, 0, 1), joint="stand-off -> deck (from below)")
        )
    return module


# --------------------------------------------------------------------------- cavities: servo power bus + MCU
CAVITY_Y = {"front": (-139.2, -69.2), "rear": (90.8, 160.8)}
BUS_BAY = (30.4, 19.2)  # one WAGO 221-415 bay (y length, x depth) incl. clearance
BUS_DIVIDER = 6.0
BUS_CENTRE_X = -5.0
BUS_BASE = 2.5
XIAO_ROTATION = rotation([(0, 1, 0), (1, 0, 0), (0, 0, -1)])  # XIAO x -> +Y (USB to the rear), pins up


def _bus_layout(side: str):
    y0, y1 = CAVITY_Y[side]
    mid = (y0 + y1) / 2
    bay_a = (mid - BUS_DIVIDER / 2 - BUS_BAY[0], mid - BUS_DIVIDER / 2)
    bay_b = (mid + BUS_DIVIDER / 2, mid + BUS_DIVIDER / 2 + BUS_BAY[0])
    return mid, bay_a, bay_b


def _bus_holder_mesh(side: str):
    mid, bay_a, bay_b = _bus_layout(side)
    x0, x1 = BUS_CENTRE_X - BUS_BAY[1] / 2 - 1.6, BUS_CENTRE_X + BUS_BAY[1] / 2 + 1.6
    z0 = LOWER_SHOULDER_TOP_Z
    base = box(x0, bay_a[0], z0, x1, bay_b[1], z0 + BUS_BASE)
    back = box(x0, bay_a[0], z0, x0 + 1.6, bay_b[1], z0 + BUS_BASE + 12.0)  # back wall (wire entries face +x)
    divider = box(x0, mid - BUS_DIVIDER / 2, z0, x1, mid + BUS_DIVIDER / 2, z0 + BUS_BASE + 8.0)
    shape = base.union(back).union(divider)
    if side == "front":
        # XIAO platform cantilevered over bay A from a raised divider
        top = z0 + BUS_BASE + 16.8 + 1.0
        riser = box(x0, mid - BUS_DIVIDER / 2, z0, x0 + 6.0, mid + BUS_DIVIDER / 2, top)
        platform = box(BUS_CENTRE_X - 11.0, bay_a[0] + 4.0, top, BUS_CENTRE_X + 11.0, mid + BUS_DIVIDER / 2, top + 2.5)
        rails = []
        for dx in (-8.89 + 1.0, 8.89 - 1.0):  # under the two long PCB edges of the flipped XIAO
            rails.append(
                box(
                    BUS_CENTRE_X + dx - 1.0,
                    bay_a[0] + 6.0,
                    top + 2.5,
                    BUS_CENTRE_X + dx + 1.0,
                    bay_a[0] + 27.0,
                    top + 6.5,
                )
            )
        stop = box(BUS_CENTRE_X - 9.0, bay_a[0] + 4.0, top + 2.5, BUS_CENTRE_X + 9.0, bay_a[0] + 6.0, top + 7.5)
        shape = shape.union(riser).union(platform).union(stop)
        for rail in rails:
            shape = shape.union(rail)
    cuts = [cylinder((BUS_CENTRE_X, mid, z0), (0, 0, 1), 1.7, -1, 30)]
    # screw-driver access from above: a 6.2 mm slot through the 6 mm divider (a 6.2 mm bore would leave
    # 0.1 mm slivers on both divider faces)
    access = box(
        BUS_CENTRE_X - 3.1,
        mid - BUS_DIVIDER / 2 - 1.0,
        z0 + BUS_BASE + 4.0,
        BUS_CENTRE_X + 3.1,
        mid + BUS_DIVIDER / 2 + 1.0,
        z0 + 40,
    )
    cuts.append(access)
    for bay in (bay_a, bay_b):  # cable-tie slots under each bay
        for y in (bay[0] + 7.0, bay[1] - 7.0):
            cuts.append(box(x0 - 1, y - 2.0, z0 + 0.6, x1 + 1, y + 2.0, z0 + 1.9))
    return boolean(to_mesh(shape), cut=cuts)


def _frame_with_pilot(side: str):
    mid, _, _ = _bus_layout(side)
    select = (lambda m: m.bounds[0][1] < 0) if side == "front" else (lambda m: m.bounds[0][1] > 0)
    frame = upstream_world("printed/lower_shoulder_frame", select)
    pilot = cylinder((BUS_CENTRE_X, mid, LOWER_SHOULDER_TOP_Z), (0, 0, 1), 1.3, -9.0, 0.5)
    return boolean(frame, cut=[pilot])


def cavity_module(side: str) -> Module:
    module = Module(f"{side} cavity")
    mid, bay_a, bay_b = _bus_layout(side)
    module.parts.append(
        NewPart(
            f"printed/lower_shoulder_frame_{side}",
            f"Lower shoulder frame ({side}, bus-holder pilot)",
            _frame_with_pilot(side),
            replaces="printed/lower_shoulder_frame",
            note="upstream Lower_Shoulder_Frame + one M3 pilot hole for the servo-bus holder",
        )
    )
    module.parts.append(
        NewPart(
            f"printed/servo_bus_holder_{side}",
            f"Servo power bus holder ({side})",
            _bus_holder_mesh(side),
            print_down=(0, 0, -1),
        )
    )
    module.fasteners.append(
        Fastener(
            "iso4762_m3x12",
            (BUS_CENTRE_X, mid, LOWER_SHOULDER_TOP_Z + BUS_BASE + 4.0),
            (0, 0, -1),
            joint="bus holder -> lower shoulder frame (self-tapping)",
        )
    )
    wago = rotation([(0, 1, 0), (-1, 0, 0), (0, 0, 1)])  # 30 mm width along +Y, 18.8 depth along -X
    for k, bay in enumerate((bay_a, bay_b)):
        for layer in range(2):
            matrix = (
                translation((BUS_CENTRE_X + 9.4, bay[0] + 0.2, LOWER_SHOULDER_TOP_Z + BUS_BASE + 8.4 * layer)) @ wago
            )
            rail = "V+" if layer == 1 else "GND"
            module.vendors.append(VendorPlacement("wago_221_415", matrix, label=f"WAGO 221-415 {side} {rail} {k}"))
    if side == "front":
        top = LOWER_SHOULDER_TOP_Z + BUS_BASE + 16.8 + 1.0 + 2.5 + 4.0
        xiao = translation((BUS_CENTRE_X - 8.89, bay_a[0] + 6.0, top + 1.25)) @ XIAO_ROTATION
        module.vendors.append(VendorPlacement("seeed_xiao_esp32s3", xiao, label="Seeed XIAO ESP32S3 (pins up)"))
    return module
