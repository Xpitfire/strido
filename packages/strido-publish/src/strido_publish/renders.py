"""Hero, exploded and section renders of the verified assembly -> docs/images/.

    make renders

* hero_front.png / hero_rear.png  standing pose, product colours
* exploded.png                    modules pulled apart along their assembly direction
* section_side.png                cut on the body mid-plane (x = -5 mm STEP): deck, battery, cavities
* section_top.png                 cut just under the top shell (z = 100 mm STEP): bay layout
* xray_top.png                    shells transparent, electronics highlighted
* wiring.png                      shells, top sensors and upper frames off: the routed harness in place
"""

from dataclasses import replace

import numpy as np
from PIL import Image

from strido.workspace import path
from strido_cad import assembly, catalog
from strido_verify.poses import stand_pose

from . import face, scene

OUT = path("docs/images")
CENTRE = np.array([-5.0, 20.8, 78.7])  # STEP frame: +x robot left, +y robot rear, +z up
ELECTRONICS = (
    "raspberry_pi_5",
    "adafruit_pca9685",
    "adafruit_lsm6dsox",
    "adafruit_ina260",
    "pololu_d36v50f5",
    "pololu_power_switch_hp",
    "seeed_xiao_esp32s3",
    "hobbywing_ubec_10a",
    "lipo_2s_5000_gensace",
    "wago_221_415",
    "fuse_holder_ato",
    "rplidar_usb_adapter",
)
# Hidden for the wiring view: everything that covers the cavities and the deck from above
COVERS = {
    "top_shell_sensor",
    "lidar_pedestal",
    "rplidar_c1",
    "rplidar_usb_adapter",
    "front_shell_display",
    "back_shell_button",
    "upper_shoulder_frame",
    "camera_mount_base",
    "camera_tilt_plate",
    "rpi_camera_module_3_wide",
}


def kind(instance) -> str:
    return instance.part.split("/")[1]


def standing():
    pose = {name: stand_pose(name, 0.17) for name in assembly.LEG_NAMES}
    return assembly.posed(catalog.full_assembly(), pose)


def explode(instances):
    """Shells and sensors up/out, legs sideways, deck electronics up."""
    moved = []
    for item in instances:
        name = kind(item)
        offset = np.zeros(3)
        if item.body != "base":
            side = 1.0 if item.body.startswith(("FL", "RL")) else -1.0
            offset = np.array([side * 90.0, 0.0, 0.0])
        elif name in ("top_shell_sensor", "lidar_pedestal"):
            offset = np.array([0.0, 0.0, 110.0])
        elif name in ("rplidar_c1", "rplidar_usb_adapter") or (
            item.meta.get("module") == "top sensors" and item.kind == "fastener"
        ):
            offset = np.array([0.0, 0.0, 170.0])
        elif name in ("front_shell_display", "waveshare_lcd_2inch", "display_bracket") or item.meta.get("module") in (
            "front display",
            "front camera",
        ):
            offset = np.array([0.0, -110.0, 30.0])
        elif (
            name in ("back_shell_button", "pushbutton_12mm", "arming_port_bezel", "arming_port_ring", "xt60h_female")
            or item.meta.get("module") == "rear panel"
        ):
            offset = np.array([0.0, 100.0, 20.0])
        elif name in ("bottom_shell", "lipo_2s_5000_gensace") or item.meta.get("joint") == "shell_to_shoulder_bottom":
            offset = np.array([0.0, 0.0, -110.0 if name == "bottom_shell" or item.kind == "fastener" else -60.0])
        elif item.meta.get("module") == "electronics deck" and name not in ("electronics_deck",):
            offset = np.array([0.0, 0.0, 45.0])
        if np.any(offset):
            matrix = item.matrix.copy()
            matrix[:3, 3] += offset
            item = replace(item, matrix=matrix)
        moved.append(item)
    return moved


def job(objects, camera, output, style="beauty", resolution=(1920, 1280), line_thickness=1.0, quads=()):
    """One Blender render; beauty shots get a transparent background (light and dark pages, PDF cover)."""
    return {
        "style": style,
        "objects": objects,
        "camera": camera,
        "output": str(OUT / output),
        "resolution": list(resolution),
        "line_thickness": line_thickness,
        "quads": list(quads),
        "transparent": style == "beauty",
    }


def face_quad(offset=(0.0, 0.0, 0.0)) -> dict:
    """The LCD face (firmware default expression) on the panel; `offset` follows the exploded front module."""
    return {"name": "lcd_face", "corners_mm": face.corners_mm(offset), "image": str(face.face_png()), "emission": 1.8}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    robot = standing()
    target = CENTRE + np.array([0.0, 0.0, -40.0])
    jobs = [
        job(
            scene.objects(robot),
            scene.camera(target, -50.0, 22.0, 1400.0, lens=85),
            "hero_front.png",
            quads=[face_quad()],
        ),
        job(
            scene.objects(robot),
            scene.camera(target, -90.0, 12.0, 1400.0, lens=85),
            "front.png",
            quads=[face_quad()],
            resolution=(1600, 1200),
        ),
        job(scene.objects(robot), scene.camera(target, 140.0, 25.0, 1400.0, lens=85), "hero_rear.png"),
        job(
            scene.objects(explode([i for i in robot if i.kind != "cable"])),  # the parts view: no wiring
            scene.camera(target + np.array([0, 0, 70]), -50.0, 24.0, 1500.0, ortho_scale=720.0),
            "exploded.png",
            quads=[face_quad((0.0, -110.0, 30.0))],
        ),
        job(
            scene.objects(robot, section=(CENTRE, np.array([1.0, 0.0, 0.0]))),
            scene.camera(CENTRE, 0.0, 8.0, 1200.0, ortho_scale=420.0),
            "section_side.png",
            resolution=(1920, 1100),
        ),
        job(
            scene.objects(
                [i for i in robot if i.body == "base"], section=(np.array([0.0, 0.0, 100.0]), np.array([0.0, 0.0, 1.0]))
            ),
            scene.camera(CENTRE, -90.0, 89.0, 1200.0, ortho_scale=360.0),
            "section_top.png",
            resolution=(1400, 1600),
        ),
        job(
            scene.objects([i for i in robot if i.body == "base"], style="xray", highlight=set(ELECTRONICS)),
            scene.camera(CENTRE, -90.0, 89.0, 1200.0, ortho_scale=360.0),
            "xray_top.png",
            style="xray",
            resolution=(1400, 1600),
        ),
        job(
            scene.objects(robot, hide=COVERS),
            scene.camera(target + np.array([0, 0, 30]), -55.0, 52.0, 1300.0, lens=85),
            "wiring.png",
            resolution=(1920, 1280),
        ),
    ]
    scene.run(jobs, "renders")
    for item in jobs:
        with Image.open(item["output"]) as image:
            if image.mode == "RGBA":  # transparent product shot: palette with alpha
                palette = image.quantize(
                    colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG
                )
            else:
                palette = image.convert("RGB").quantize(
                    colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG
                )
        palette.save(item["output"], optimize=True)  # ~4x smaller, no visible banding at 256 colours
        print(item["output"])


if __name__ == "__main__":
    main()
