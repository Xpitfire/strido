"""The print kit people send to a printer: complete, closed, and fits the stated bed."""

import re
import zipfile
from collections import Counter

import trimesh

from strido.workspace import path
from strido_cad.geom import to_manifold

BED_MM = (220.0, 220.0, 250.0)
# table row of the generated print list: | part | qty | colour | `file` | ... (file relative to hardware/print/)
ROW = re.compile(r"^\| (\w+) \| (\d+) \| [^|]+ \| `([^`]+)` \|")
# 3MF build item label written by strido_publish.print_files: partnumber="part_<name>_<n>"
PART_NUMBER = re.compile(r'partnumber="part_(\w+?)_\d+"')


def print_rows() -> list[tuple[str, str, str]]:
    lines = path("hardware/print/print_list.md").read_text().splitlines()
    return [match.groups() for match in map(ROW.match, lines) if match]


def test_every_listed_part_has_a_closed_stl_in_the_kit_that_fits_the_bed():
    rows = print_rows()
    assert len(rows) >= 30
    for name, _, file in rows:
        assert file == f"stl/{name}.stl", f"{name} is not in the self-contained kit"
        mesh = trimesh.load_mesh(path(f"hardware/print/{file}"))
        assert to_manifold(mesh).status().name == "NoError", f"{name}: not a closed manifold"
        footprint = sorted(mesh.extents[:2])
        assert footprint[1] <= BED_MM[0] and mesh.extents[2] <= BED_MM[2], f"{name}: {mesh.extents} exceeds the bed"


def test_plates_carry_every_piece_exactly_once():
    expected = Counter({name: int(qty) for name, qty, _ in print_rows()})
    plated: Counter[str] = Counter()
    for plate in path("hardware/print/plates").glob("*.3mf"):
        model = zipfile.ZipFile(plate).read("3D/3dmodel.model").decode()
        plated.update(PART_NUMBER.findall(model))
    assert plated == expected
