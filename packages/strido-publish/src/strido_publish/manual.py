"""IKEA-style assembly manual generated from the verified CAD assembly.

Every instance of the full assembly (printed part, purchased part, fastener) is
assigned to exactly one step; the build fails if anything is unassigned or
assigned twice, so the parts boxes add up to the complete robot.

Outputs
  docs/assembly/README.md          Markdown manual (GitHub / docs site)
  docs/assembly/img/step_XX.png    step drawings (Blender + Freestyle)
  docs/assembly/img/parts/*.png    part icons
The A4 book (catalogue + these steps) is `strido_publish.book`.

    make manual                                   # everything
    python -m strido_publish.manual --no-render  # text only (reuse images)
"""

import argparse
import html
from collections import Counter
from dataclasses import replace

import numpy as np
import trimesh
from PIL import Image

from strido.workspace import path, repo_root
from strido_cad import catalog

from . import scene
from .manual_select import Step, is_fl, kind
from .manual_steps import STEPS, assign
from .part_titles import title

REPO = repo_root()
OUT = path("docs/assembly")
IMG = OUT / "img"
ICONS = IMG / "parts"
EXPLODE_FASTENER_MM = 16.0


def exploded(instance, step: Step, centre) -> np.ndarray:
    if instance.kind == "fastener":
        axis = instance.matrix[:3, 2]
        sign = -1.0 if kind(instance).startswith("iso4762") or kind(instance).startswith("iso7089") else 1.0
        offset = sign * axis * EXPLODE_FASTENER_MM
    else:
        if kind(instance) in step.anchor:
            return instance.matrix
        offset = np.array(step.explode, dtype=float)
        if step.radial:
            axis_index = "xyz".index(step.radial.lstrip("-"))
            mesh = trimesh.load(instance.mesh, force="mesh")
            point = trimesh.transform_points([mesh.bounds.mean(axis=0)], instance.matrix)[0]
            direction = np.zeros(3)
            direction[axis_index] = 1.0 if point[axis_index] >= centre[axis_index] else -1.0
            offset = offset + direction * (-30.0 if step.radial.startswith("-") else 30.0)
    if np.allclose(offset, 0):
        return instance.matrix
    moved = instance.matrix.copy()
    moved[:3, 3] += offset
    return moved


def world_bounds(instances):
    lows, highs = [], []
    for instance in instances:
        mesh = trimesh.load(instance.mesh, force="mesh")
        corners = trimesh.transform_points(trimesh.bounds.corners(mesh.bounds), instance.matrix)
        lows.append(corners.min(axis=0))
        highs.append(corners.max(axis=0))
    return np.min(lows, axis=0), np.max(highs, axis=0)


def render_jobs(groups):
    centre = np.array([-5.0, 20.8, 78.7])
    jobs = []
    built = []
    for index, (step, new) in enumerate(zip(STEPS, groups), start=1):
        shown_new = [i for i in new if is_fl(i)] if step.per_leg or step.scope == "leg" else new
        if step.scope == "leg":
            context = [i for i in built if is_fl(i)]
        elif step.scope == "bench":
            context = []
        else:
            context = list(built)
        moved = [replace(i, matrix=exploded(i, step, centre)) for i in shown_new]
        low, high = world_bounds(context + shown_new + moved)
        target = (low + high) / 2
        size = float(np.linalg.norm(high - low)) * 0.85 / step.zoom
        arrows = []
        for original, shifted in zip(shown_new, moved):
            start = shifted.matrix[:3, 3]
            end = original.matrix[:3, 3]
            if np.linalg.norm(end - start) > 1.0 and original.kind != "fastener":
                mesh = trimesh.load(original.mesh, force="mesh")
                centre_local = mesh.bounds.mean(axis=0)
                arrows.append(
                    {
                        "from": trimesh.transform_points([centre_local], shifted.matrix)[0].tolist(),
                        "to": trimesh.transform_points([centre_local], original.matrix)[0].tolist(),
                        "radius_mm": 0.9,
                    }
                )
        objects = scene.objects(context, style="ikea") + scene.objects(
            moved, style="ikea", highlight={i.id for i in moved}
        )
        jobs.append(
            {
                "style": "ikea",
                "objects": objects,
                "arrows": arrows,
                "line_thickness": 1.3,
                "resolution": [1600, 1200],
                "camera": scene.camera(target, step.view[0], step.view[1], 1500.0, ortho_scale=size),
                "output": str(IMG / f"step_{index:02d}.png"),
            }
        )
        built.extend(new)
    return jobs


def icon_jobs(groups):
    seen = {}
    for new in groups:
        for instance in new:
            if instance.kind != "cable":  # cables have no parts-box entry
                seen.setdefault(kind(instance), instance)
    jobs = []
    for name, instance in sorted(seen.items()):
        mesh = trimesh.load(instance.mesh, force="mesh")
        rotation = instance.matrix.copy()
        rotation[:3, 3] = 0.0
        corners = trimesh.transform_points(trimesh.bounds.corners(mesh.bounds), rotation)
        target = (corners.min(axis=0) + corners.max(axis=0)) / 2
        size = float(np.linalg.norm(corners.max(axis=0) - corners.min(axis=0))) * 0.9
        placed = replace(instance, matrix=rotation)
        jobs.append(
            {
                "style": "ikea",
                "objects": scene.objects([placed], style="ikea", highlight={instance.id}),
                "line_thickness": 1.0,
                "resolution": [256, 256],
                "camera": scene.camera(target, -45.0, 30.0, 800.0, ortho_scale=max(size, 8.0)),
                "output": str(ICONS / f"{name}.png"),
            }
        )
    return jobs


def parts_box(new, per_leg: bool) -> list[tuple[str, int, str]]:
    """(part, quantity, label); per-leg steps count one leg and name the legs of mirrored parts."""
    order = {"printed": 0, "purchased": 1, "fastener": 2}
    new = [i for i in new if i.kind != "cable"]  # cables: cut list in the wiring check, not parts boxes
    kinds = {kind(i): i.kind for i in new}
    legs = {}
    for instance in new:
        legs.setdefault(kind(instance), set()).add(instance.body.split(".")[0])
    counts = Counter(kind(i) for i in new)
    rows = []
    for name, count in sorted(counts.items(), key=lambda item: (order.get(kinds[item[0]], 3), item[0])):
        label = title(name)
        if per_leg:
            used_by = sorted(legs[name])
            assert count % len(used_by) == 0, f"{name}: {count} pieces do not split evenly over legs {used_by}"
            count //= len(used_by)
            if len(used_by) < 4:
                label += f" – legs {', '.join(used_by)} only"
        rows.append((name, count, label))
    return rows


PREPARATION = """## Step 0 – Before you start

* Print every part in the [print list](../../hardware/print/print_list.md) (easiest: the [print kit](../print-kit.md) package with the ready plates). Remove supports and brims; test-fit bearings (625ZZ, 633ZZ, 6805-2RS) and sleeves before assembly.
* Wiring: every cable is drawn in the steps that install it; lengths are in the [cut list](../verification/wiring.md#cut-list) and the build order in [electronics › wiring harness](../electronics.md#wiring-harness). Set both UBECs to 6.0 V and measure them before any servo is connected.
* **Centre all 12 servos** before fitting any horn. Bench set-up: XIAO (flashed with `firmware/strido_esp32s3`) on USB to your computer, PCA9685 on I²C with its OE pull-up, servo power from one UBEC at 6.0 V (or a 6 V bench supply) to the servo's red/black wires, signal to the PCA9685 channel it will use. Run `strido-cli --port <usb port> center` (1500 µs on every channel; works without the INA260 and stops with an error if the controller is not driving). A centred servo is the assembly reference: hip leg vertical, femur 45° backwards, knee crank 35°.
* Tools: hex keys 1.5 / 2.0 / 2.5 mm, nut drivers 4.0 / 5.0 / 5.5 mm, flush cutters, soldering iron and solder, multimeter, crimp tool for Dupont, medium thread locker for screws into metal horns.
* Screws into printed holes marked *self-tapping*: turn until snug, never to full torque. Metal-to-metal screws (horns): one drop of medium thread locker.
"""

FINISH = """## Step {index} – Wiring, calibration and first power-up

1. Check the harness against [electronics › wiring harness](../electronics.md#wiring-harness) (W00–W23, servo leads S-*): every joint soldered and heat-shrunk, no strands outside a WAGO or terminal. Keep the fuses and the arming loop key out.
2. Fuses in, press the power button: the Pi boots, the face appears on the LCD, `ros2 topic echo /battery_state` shows the pack voltage. The servos stay limp: the controller keeps the PCA9685 outputs off until it receives position commands.
3. Fine-calibrate each joint with `strido-cli calibrate` (robot on a stand, legs free; offsets stored in the ESP32 flash).
4. Lay the robot on its belly with the legs folded (the rest pose), insert the loop key (servos stay limp), then start `ros2 launch strido_bringup robot.launch.py`: the servos move to the rest pose and the robot stands up within 3 s. Never insert the key while position commands are running: all 12 servos would jump at once (up to 6 × 3.5 A stall per cavity against a 15 A UBEC peak).
5. Teleoperate: `ros2 run teleop_twist_keyboard teleop_twist_keyboard`. Publish `true` on `/strido/estop` to stop. After releasing an e-stop or a relax, restart the launch with the robot lying in the rest pose: the gait node only ramps up on start.
"""


def write_markdown(groups):
    lines = [
        "# Assembly manual",
        "",
        "Generated from the verified CAD assembly by `strido_publish.manual`: every printed part, purchased part and fastener modelled in the CAD appears in exactly one parts box "
        "(cables are drawn in the steps that lay them; their lengths are in the [cut list](../verification/wiring.md#cut-list), consumables in the [shop](../shop.md)). "
        "Leg steps show the front-left leg; build all four (quantities are per leg). Highlighted parts are new in the step; arrows show where they go.",
        "",
        PREPARATION,
    ]
    for index, (step, new) in enumerate(zip(STEPS, groups), start=1):
        lines += [
            f"## Step {index} – {step.title}" + (" (×4 legs)" if step.per_leg else ""),
            "",
            f"![Step {index}](img/step_{index:02d}.png)",
            "",
            "<table>",
        ]
        for name, count, label in parts_box(new, step.per_leg):
            lines.append(
                f'<tr><td><img src="./img/parts/{name}.png" width="56"></td><td><b>{count}×</b></td><td>{html.escape(label)}</td></tr>'
            )
        lines += ["</table>", ""]
        lines += [f"{n}. {text}" for n, text in enumerate(step.instructions, start=1)]
        lines.append("")
    lines.append(FINISH.format(index=len(STEPS) + 1))
    (OUT / "README.md").write_text("\n".join(lines))


def markdown_inline(text: str) -> str:
    """Escape text, turn `code` spans into <code> and *emphasis* (outside code) into <em> (split, no regex)."""
    pieces = html.escape(text).split("`")
    return "".join(f"<code>{piece}</code>" if index % 2 else emphasis(piece) for index, piece in enumerate(pieces))


def emphasis(text: str) -> str:
    pieces = text.split("*")
    if len(pieces) % 2 == 0:  # unpaired asterisk: leave the text as written
        return text
    return "".join(f"<em>{piece}</em>" if index % 2 else piece for index, piece in enumerate(pieces))


def compress_images() -> None:
    """Line drawings need few colours: a 96-colour palette cuts the PNGs ~5x without visible loss."""
    for image_path in sorted(IMG.glob("step_*.png")) + sorted(ICONS.glob("*.png")):
        with Image.open(image_path) as image:
            if image.mode == "P":
                continue
            palette = image.convert("RGB").quantize(
                colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
            )
        palette.save(image_path, optimize=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args()
    instances = catalog.full_assembly()
    groups = assign(instances)
    total = sum(len(g) for g in groups)
    print(f"{total} instances in {len(STEPS)} steps")
    OUT.mkdir(parents=True, exist_ok=True)
    if not args.no_render:
        ICONS.mkdir(parents=True, exist_ok=True)
        scene.run(icon_jobs(groups), "manual_icons")
        scene.run(render_jobs(groups), "manual_steps")
        compress_images()
    write_markdown(groups)


if __name__ == "__main__":
    main()
