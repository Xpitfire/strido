"""Strido stiff long link (ADR-010): the knee linkage's long link, 10 mm wide in the leg plane.

The upstream Long_Link is 5 mm wide in the leg plane: with the knee servo at stall it buckles at about
65 N while the worst pose drives it with 192 N (strido_verify.strength). This link keeps what the
linkage depends on: the two pin bores (sleeve-bearing pairs 3 x 5 x 5) 131 mm apart, the upstream eyes
(7 mm across) and the 10 mm eye thickness along the pins. The shaft is 10 mm wide in the leg plane and
10 mm thick over its whole length (upstream: 5 x 8 mm), so the link prints flat with vertical bores and no
supports.

The shaft's centre line sits 2 mm off the pin line, away from the femur: with the knee stretched the femur
passes 4.1 mm beside the pin line, and the short link and its washer pass close to the crank-side eye at
full flex. Offset, every neighbour keeps at least 1 mm in every pose of the range-of-motion grid (measured
when the link was designed); centred, the femur came within 0.25 mm and the joint limits shrank by 5 deg.

Built in the frame of the upstream STL (pins along z, length along y), so it replaces every upstream
instance with the same placement.
"""

import json
from dataclasses import replace

import cadquery as cq
import trimesh

from . import assembly
from .geom import cylinder, to_mesh
from .paths import CAD_CACHE

UPSTREAM = "printed/long_link"
PART = "printed/stiff_long_link"
PIN_Y_MM = (50.0, -81.0)  # bore centres in Long_Link.stl (x = 0); pins along z
BORE_DIAMETER_MM = 5.0  # sleeve-bearing pair 3 x 5 x 5 per eye
EYE_RADIUS_MM = 3.5  # upstream eyes: 1 mm wall around the bore on the femur side
THICKNESS_Z_MM = (-7.5, 2.5)  # along the pins: the upstream eye thickness
WIDTH_MM = 10.0  # in the leg plane (upstream shaft: 5 mm)
SHAFT_OFFSET_X_MM = 2.0  # shaft centre line off the pin line, away from the femur (+x)
CACHE = CAD_CACHE / "parts"


def link_mesh() -> trimesh.Trimesh:
    """The stiff long link in the upstream Long_Link.stl frame: an offset stadium plus the upstream eyes, minus
    the pin bores."""
    top, bottom = PIN_Y_MM
    low, high = THICKNESS_Z_MM
    link = (
        cq.Workplane("XY")
        .workplane(offset=low)
        .center(SHAFT_OFFSET_X_MM, (top + bottom) / 2)
        .slot2D(top - bottom + WIDTH_MM, WIDTH_MM, angle=90)
        .extrude(high - low)
    )
    for pin in PIN_Y_MM:
        link = link.union(cylinder((0.0, pin, 0.0), (0, 0, 1), EYE_RADIUS_MM, low, high))
    for pin in PIN_Y_MM:  # cutters reach 1 mm past both faces so no face is shared
        link = link.cut(cylinder((0.0, pin, 0.0), (0, 0, 1), BORE_DIAMETER_MM / 2, low - 1.0, high + 1.0))
    return to_mesh(link)


def replace_long_links(instances: list[assembly.Instance]) -> list[assembly.Instance]:
    """Every upstream long link becomes the stiff long link, at the same placement."""
    target = CACHE / "stiff_long_link.stl"
    stamp = CACHE / "stiff_long_link.key"
    key = json.dumps([PIN_Y_MM, BORE_DIAMETER_MM, EYE_RADIUS_MM, THICKNESS_Z_MM, WIDTH_MM, SHAFT_OFFSET_X_MM])
    if not target.is_file() or not stamp.is_file() or stamp.read_text() != key:
        CACHE.mkdir(parents=True, exist_ok=True)
        link_mesh().export(target)
        stamp.write_text(key)
    note = f"upstream long_link, {WIDTH_MM:.0f} x 10 mm instead of 5 x 8 mm, same pins and eyes: buckling, ADR-010"
    return [
        replace(
            item,
            part=PART,
            mesh=target,
            meta={**item.meta, "source": "strido derived", "derived_from": UPSTREAM, "derived_note": note},
        )
        if item.part == UPSTREAM
        else item
        for item in instances
    ]
