"""NT-X integration smoke: load the Strido extension inside the real NT-X harness environment.

    make ntx-smoke                                  # NTX_HARNESS=../../ntx-harness by default
    python -m strido_ntx.smoke --ntx-harness PATH

Runs `strido_ntx.smoke_inner` with the NT-X project environment plus editable Strido
packages layered on top by `uv run --with-editable` (the NT-X virtualenv is not modified).
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from strido.workspace import repo_root


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ntx-harness", type=Path, required=True, help="path to the ntx-harness checkout")
    args = parser.parse_args()
    harness = args.ntx_harness.resolve()
    if not (harness / "pyproject.toml").is_file():
        sys.exit(f"ntx-smoke: {harness} is not an ntx-harness checkout (set NTX_HARNESS)")
    root = repo_root()
    command = [
        "uv",
        "run",
        "--project",
        str(harness),
        "--frozen",
        "--with-editable",
        str(root / "packages/strido-core"),
        "--with-editable",
        str(root / "packages/strido-ntx"),
        "python",
        "-m",
        "strido_ntx.smoke_inner",
    ]
    environment = {
        key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"
    }  # run in the NT-X project env
    sys.exit(subprocess.run(command, cwd=harness, env=environment, check=False).returncode)


if __name__ == "__main__":
    main()
