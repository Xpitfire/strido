"""Read an XCAF STEP assembly into a flat list of located leaf solids.

The upstream Yertle STEP (`upstream/yertle/design/CAD/Yertle_Single_v2.step`) is the only source
that places every part in its assembled position. This module flattens its
assembly tree so other tools can tessellate, measure or register parts against
it without re-implementing the XCAF traversal.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDF import TDF_Label, TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS_Shape
from OCP.XCAFDoc import XCAFDoc_DocumentTool


@dataclass
class LeafSolid:
    """One located leaf shape of the assembly, in assembly (world) millimetres."""

    path: tuple[str, ...]
    name: str
    shape: TopoDS_Shape
    volume_mm3: float
    centroid_mm: np.ndarray
    bbox_min_mm: np.ndarray
    bbox_max_mm: np.ndarray

    @property
    def path_str(self) -> str:
        return "/".join(self.path)


def _label_name(label: TDF_Label) -> str:
    attribute = TDataStd_Name()
    if label.FindAttribute(TDataStd_Name.GetID_s(), attribute):
        return attribute.Get().ToExtString()
    return "unnamed"


def read_step_leaves(step_path: Path) -> list[LeafSolid]:
    """Return every non-empty leaf solid of the STEP assembly with its world placement."""
    assert step_path.is_file(), step_path
    document = TDocStd_Document(TCollection_ExtendedString("yertle"))
    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    assert reader.ReadFile(str(step_path)) == 1, f"cannot read {step_path}"
    assert reader.Transfer(document), f"cannot transfer {step_path}"
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())

    leaves = []
    # Explicit stack instead of recursion: (definition label, accumulated location, path).
    roots = TDF_LabelSequence()
    shape_tool.GetFreeShapes(roots)
    stack = [(roots.Value(i), TopLoc_Location(), (_label_name(roots.Value(i)),)) for i in range(1, roots.Length() + 1)]
    max_nodes = 100_000
    visited = 0
    while stack:
        visited += 1
        assert visited < max_nodes, "assembly traversal did not terminate"
        definition, location, path = stack.pop()
        if shape_tool.IsAssembly_s(definition):
            components = TDF_LabelSequence()
            shape_tool.GetComponents_s(definition, components)
            for index in range(1, components.Length() + 1):
                component = components.Value(index)
                referred = TDF_Label()
                shape_tool.GetReferredShape_s(component, referred)
                child_location = location.Multiplied(shape_tool.GetLocation_s(component))
                stack.append((referred, child_location, (*path, _label_name(component))))
            continue
        shape = shape_tool.GetShape_s(definition).Located(location)
        box = Bnd_Box()
        BRepBndLib.Add_s(shape, box)
        if box.IsVoid():
            continue
        properties = GProp_GProps()
        BRepGProp.VolumeProperties_s(shape, properties)
        centre = properties.CentreOfMass()
        x_min, y_min, z_min, x_max, y_max, z_max = box.Get()
        leaves.append(
            LeafSolid(
                path=path,
                name=_label_name(definition),
                shape=shape,
                volume_mm3=properties.Mass(),
                centroid_mm=np.array([centre.X(), centre.Y(), centre.Z()]),
                bbox_min_mm=np.array([x_min, y_min, z_min]),
                bbox_max_mm=np.array([x_max, y_max, z_max]),
            )
        )
    leaves.sort(key=lambda leaf: leaf.path_str)
    return leaves
