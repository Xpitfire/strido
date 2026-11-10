"""Tracked inputs and generated outputs of the CAD pipeline (repository-relative)."""

from strido.workspace import repo_root

REPO = repo_root()

# Upstream Yertle design (MIT, Jerome Graves): STEP assembly and print STLs
UPSTREAM_DESIGN = REPO / "upstream/yertle/design"
UPSTREAM_STEP = UPSTREAM_DESIGN / "CAD/Yertle_Single_v2.step"
UPSTREAM_STL = UPSTREAM_DESIGN / "STL"

# Tracked hardware data (single sources of truth)
HARDWARE = REPO / "hardware"
KINEMATICS = HARDWARE / "kinematics.yaml"
JOINT_LIMITS = HARDWARE / "joint_limits.yaml"
FASTENER_CATALOGUE = HARDWARE / "fasteners.yaml"
FASTENER_RULES_UPSTREAM = HARDWARE / "fasteners_upstream.yaml"
MASS_PROPERTIES = HARDWARE / "mass_properties.yaml"
UPSTREAM_PLACEMENTS = HARDWARE / "assembly/upstream_placements.yaml"
CORRECTIONS = HARDWARE / "assembly/corrections.yaml"

# Generated, untracked
BUILD = REPO / "build"
CAD_CACHE = BUILD / "cad"
VERIFY_OUT = BUILD / "verify"
HOLE_STACKS_JSON = VERIFY_OUT / "hole_stacks.json"
UPSTREAM_FASTENERS_JSON = VERIFY_OUT / "fasteners_upstream.json"
