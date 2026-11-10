"""Selectors of the assembly manual: which instances a step fits (predicates) and the step record.

`strido_publish.manual_steps` lists the steps with these; the manual, the viewer and the book use
`kind` to name a part.
"""

from collections.abc import Callable
from dataclasses import dataclass

from strido_cad import assembly

LEG_SHOWN = "FL"

Predicate = Callable[[assembly.Instance], bool]


def kind(instance) -> str:
    return instance.part.split("/")[1]


def types(*names) -> Predicate:
    return lambda i: kind(i) in names


def joints(*names) -> Predicate:
    return lambda i: i.kind == "fastener" and i.meta.get("joint") in names


def body_part(*parts) -> Predicate:
    """Leg body by its suffix: hip, thigh, crank, arm, calf, long_link, short_link (all four legs); cables riding
    on a leg body belong to the wiring steps."""
    return lambda i: i.kind != "cable" and "." in i.body and i.body.split(".", 1)[1] in parts


def base(predicate: Predicate) -> Predicate:
    return lambda i: i.body == "base" and predicate(i)


def either(*predicates) -> Predicate:
    return lambda i: any(p(i) for p in predicates)


def both(*predicates) -> Predicate:
    return lambda i: all(p(i) for p in predicates)


def excluding(predicate: Predicate, *excluded: Predicate) -> Predicate:
    return lambda i: predicate(i) and not any(p(i) for p in excluded)


def label(text: str) -> Predicate:
    """Purchased part whose placement label contains `text` (one of several placements of a part)."""
    return lambda i: text in i.meta.get("label", "")


def runs(*names: str) -> Predicate:
    """Cable instances of these wiring runs (a cable's trunk `W02` or a branch `W02/logic`)."""
    return lambda i: i.kind == "cable" and i.meta.get("run") in names


def cables(*ids: str) -> Predicate:
    """Cable instances (conductors, hip loops) of the wiring runs of these cables (hardware/wiring.yaml)."""
    return lambda i: i.kind == "cable" and i.meta.get("cable") in ids


def servo_leads(instance) -> bool:
    """The twelve servo leads (S-<leg>-<joint>) with their power and signal branches."""
    return instance.kind == "cable" and str(instance.meta.get("cable", "")).startswith("S-")


def dressing(instance) -> bool:
    """Spiral wrap, cable ties and adhesive tie mounts."""
    if instance.kind == "cable":
        return instance.meta.get("type") in ("spiral_wrap", "cable_tie")
    return kind(instance) == "cable_tie_mount"


SHELL_NUTS = both(types("iso4032_m3"), joints("shell_to_shoulder_top", "shell_to_shoulder_bottom"))
LEG_MOUNT = either(
    both(body_part("hip"), types("servo_disc_horn_25t")),
    joints("hip_horn", "hip_pivot"),
    both(body_part("hip"), joints("horn_centre_screw")),
)


def is_fl(instance) -> bool:
    return instance.body.startswith(f"{LEG_SHOWN}.")


@dataclass
class Step:
    title: str
    select: Predicate
    instructions: list[str]
    view: tuple = (-45.0, 28.0)  # azimuth, elevation (STEP frame: -y is the robot front, +x its left side)
    explode: tuple = (0.0, 0.0, 0.0)  # mm, applied to new non-fastener parts
    radial: str = ""  # "x"/"y": explode new parts away from the body centre along this axis, "-x"/"-y": towards it
    anchor: tuple = ()  # part types that stay in place (the part the others are fitted to)
    scope: str = "robot"  # robot | leg (front-left leg parts only) | bench (only the new parts)
    per_leg: bool = False
    zoom: float = 1.0
