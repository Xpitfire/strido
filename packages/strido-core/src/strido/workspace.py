"""Repository layout for the development tooling (CAD, verification, simulation, docs).

The robot runtime (ROS 2 nodes, bench CLI) never needs these paths; only tools that
read or write the tracked hardware data and generated artefacts do. The root is the
directory that holds ``hardware/kinematics.yaml``; ``STRIDO_REPO_ROOT`` overrides the
search (e.g. for an installed wheel that operates on a checkout elsewhere).
"""

import os
from functools import cache
from pathlib import Path

ROOT_MARKER = Path("hardware/kinematics.yaml")
MAX_PARENT_LEVELS = 12


@cache
def repo_root() -> Path:
    """Return the repository root or raise if the tooling runs outside a checkout."""
    override = os.environ.get("STRIDO_REPO_ROOT")
    if override:
        root = Path(override).resolve()
        if not (root / ROOT_MARKER).is_file():
            raise FileNotFoundError(f"STRIDO_REPO_ROOT={root} does not contain {ROOT_MARKER}")
        return root
    for start in (Path(__file__).resolve(), Path.cwd().resolve()):
        for candidate in [start, *start.parents][:MAX_PARENT_LEVELS]:
            if (candidate / ROOT_MARKER).is_file():
                return candidate
    raise FileNotFoundError(f"no Strido checkout found (looked for {ROOT_MARKER}); set STRIDO_REPO_ROOT")


def path(relative: str) -> Path:
    """Absolute path of a repository-relative location."""
    return repo_root() / relative


def build_dir(*parts: str) -> Path:
    """Generated, untracked output under ``build/`` (created on demand)."""
    directory = repo_root().joinpath("build", *parts)
    directory.mkdir(parents=True, exist_ok=True)
    return directory
