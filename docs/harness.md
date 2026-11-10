# Engineering harness runbook

> **Status:** how to work on this repository (humans and coding agents). Rules: `AGENTS.md`.

## Setup

```bash
make setup               # uv sync, docs-site npm ci, submodules, harness install (hooks, skills, MCP config)
```

Requirements: uv ≥ 0.9, Python 3.12 (managed by uv), Node 26 (`.nvmrc`), PlatformIO (`pipx install platformio`), Blender 4 for renders, Docker for Gazebo, Pango for the PDF (`brew install pango`).

## Gates

| Tier | Command | Proves | Time |
|---|---|---|---|
| Q0 | `make check-fast` | ruff, mypy (strict for core/ntx/workspace), import-linter layers, generated-file drift (geometry bindings, electronics report, NT-X assets), Python tests with coverage, firmware native tests | ~1 min |
| Q1 | `make verify` | CAD: hole stacks → fasteners, interference (4 poses), sensor FoV, ROM sweep, fits/tolerances, strength (link bending/buckling, screw shear, hole pressure, bearings, pilot torques), moving clearance | ~10 min |
| Q1 | `make printability` | every printed part and 3MF plate sliced by PrusaSlicer with `hardware/print/prusaslicer.ini` (errors, conflicts, stability issues, missing parts fail), wall-thickness scan, filament and time | ~1 min, needs PrusaSlicer |
| Q1 | `make check` | Q0 + verify + printability + BOM coverage + CAD tests + docs build + harness checks | ~13 min |
| Q2 | `make smoke` | MuJoCo walk video, MCP server over stdio, NT-X extension inside the NT-X harness | ~2 min |
| Q2 | `make sim-gazebo`, `make rl-smoke` | ROS 2 + Gazebo walk test in Docker; PPO pipeline | 5–10 min |
| Q3 | hardware | a built robot: stand, walk, measured current/runtime | — |

The pre-commit hook runs the harness self-check; CI (`.github/workflows/quality.yml`) runs Q0 and the docs build.

## Changing hardware

1. Edit the source: a CadQuery part in `packages/strido-cad/src/strido_cad/parts.py`, a placement, `hardware/*.yaml`.
2. `make cad` if kinematics or limits can change, else `make models`.
3. `make verify` — fix geometry until it passes; never widen `hardware/verification/*.yaml` to pass. Record any deliberate rule change in `docs/decisions.md`.
4. `make publish` — print kit, BOM, manual, renders, viewer, book.
5. `make check-fast`, record the run in `docs/verification.md`.

## Agent tooling

* **Skills** (`.agents/skills/`): `strido-hardware`, `strido-verification`, `strido-bringup`, `strido-docs`, `strido-ntx`, plus the harness skills (`software-engineering`, …).
* **MCP** (`.mcp.json`, `.codex/config.toml`): `strido-hardware` (part sizes, fasteners, fits, clearances, joint limits, pin map, BOM, verification status), `codegraph` (code index).
* **CLI**: `uv run strido part electronics_deck`, `strido pinout lcd`, `strido fits --status warn`, `strido clearances --max-gap 1`.

## Release

`make publish && make package` writes `dist/strido-<version>.zip` (repository + PDF + walk video). Tag `strido-v<version>`.

## Documentation site on Cortex

The site runs at **https://strido.cortex.a2olabs.com/**, public, in English and German (`/de/`). The image (`docs-site/Dockerfile`, `docker-compose.docs.yml` + `docker-compose.cortex.yml`) builds the site from the repository and bundles the downloads: the build kit ZIP (every STL, the 3MF plates, slicer profile, print list, book PDF, BOM), the book PDF, the 3D model, the Agent Skill ZIP and `llms.txt`. A second service, `assistant`, answers the AI bar and the MCP server `/mcp` from the same pages; it reaches the model through Cortex Keyring (`models` in `.cortex/app.yml`) and keeps conversations in a Docker volume. The app's own gateway route (`.cortex/access/caddy/sso/`) serves the site to everyone and sends `/api/*` and `/mcp` to the assistant behind Cortex SSO (or a Cortex app token), so the assistant's model use stays with signed-in users.

```bash
make docs & make assistant                                  # local: site with live AI bar on http://127.0.0.1:4173/
docker compose -f docker-compose.docs.yml up --build       # local images: site :4390, assistant :4391
make i18n                                                   # after English changes: new German segments to translate
git push                                                      # Cortex builds from GitHub, not from the checkout
cortex deploy --ref "$(git rev-parse HEAD)"
cortex jobs watch <job-id>
cortex apps show strido
```

The repository is public at [github.com/Xpitfire/strido](https://github.com/Xpitfire/strido). Publish only after `make publish` and `make printability`, so the downloads match the verified CAD.
