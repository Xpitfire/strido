# Downloads

> **Status:** generated from the verified CAD assembly; the files below are rebuilt with every documentation deploy. They are served by the documentation site, not by the repository view.

| Download | Contents |
|---|---|
| **[Build kit (ZIP)](/downloads/strido-build-kit.zip)** | Every printed part as an oriented STL, the ready 3MF build plates, the verified PrusaSlicer profile, the print list, the catalogue & assembly book PDF and the bill of materials |
| **[Catalogue & assembly book (A4 PDF)](/catalog/strido-catalog.pdf)** | Printed and purchased parts, hardware drawn at 1:1, shopping plan, tools, every assembly step, wiring, software appendix |
| <a href="/viewer/strido.glb" download>3D model (GLB)</a> | The complete assembled robot for any glTF viewer or Blender; interactive in the [3D viewer](viewer.md) |

## Print everything

1. Unpack the build kit and load `prusaslicer.ini` (PrusaSlicer: File › Import › Import Config). Other slicers: enter the settings from `print_list.md` (0.4 mm nozzle, 0.2 mm layers, 3 perimeters, 5 top/bottom layers, 30 % gyroid, PETG).
2. Print the plates in `plates/`: graphite plates for the frame and legs, lime plates for the shells and shoulders. Single parts: `stl/` (quantities in `print_list.md`).
3. Supports and brims as listed per part; the slicer gate in [printability](verification/printability.md) slices every part and plate with exactly this profile.

About 1 kg of PETG (one spool per colour) and roughly 100 hours of printing for the whole robot (slicer estimate).

## Source

The repository is public: [github.com/Xpitfire/strido](https://github.com/Xpitfire/strido), software under Apache-2.0 and hardware files under CERN-OHL-P-2.0. It holds the CAD pipeline, firmware, ROS 2 packages, simulation and every verification gate; `make publish` regenerates all downloads.
