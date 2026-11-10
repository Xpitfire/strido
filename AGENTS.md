<!-- harness:begin -->
# Engineering Agent Instructions

Applies to every agent session here and in template-derived repositories.

## Before deciding

- Inspect current code, tree, and effective runtime/config. Stale or unverified
  artifacts cannot override observed state or user-approved requirements.
- Query the CodeGraph MCP index first for structure, symbols, callers, and
  impact; explore by hand only what the index does not answer. The index
  persists across sessions — do not re-derive what it already knows.
- Use the `software-engineering` skill for every substantive task:
  requirements, architecture, implementation, debugging, or review. It loads
  automatically; never wait for a slash command.
- Derive before you ask. The repo, git history, the user's own sites, package
  registries, vendor docs and installed CLIs answer most factual questions.
  Before calling an external dependency blocking, check whether its CLI is
  authenticated and whether the account already holds what you need.

## While working

- Prefer the smallest correct change. Reuse native and existing capabilities
  before adding code, configuration, or dependencies. A datastore nothing
  queries, a service nothing calls, an endpoint nothing hits: build each when
  something needs it, so it never becomes the scope you delete later.
- Keep requirements and product decisions in the main conversation. Ask only
  questions whose answers change what you will build.
- Resolve root causes. Never suppress, work around, or defer an error to
  keep moving.
- Edit canonical sources; regenerate and verify derived outputs. Never
  hand-edit copies or assume config is effective.
- Re-scan shared state before mutations. Never revert, overwrite, or clean up
  work you did not make. Keep secrets out of commits, logs, and tool output.
- Follow the repo-wide service architecture standard (see the
  `software-engineering` skill's architecture reference): DTOs at API
  boundaries, data access behind DAOs/repositories, services communicate
  only through published APIs. Use repository-managed runtimes and commands;
  Python runs only through the project venv or a managed runner. Keep
  hermetic checks independent of ambient credentials and network.
- Configuration is centralized (see the skill's platform reference):
  committed non-secret env bases plus one gitignored secrets file whose keys
  are all listed in a committed example; no per-service env files, no
  environment literals in code.
- Infrastructure keeps three tiers (platform reference): leaf modules → one
  root stack → thin per-environment roots. Topology is declared data, secrets
  are injected, and generated config carries a drift check.
- Delegate independent read-heavy work (exploration, research, review) to
  subagents; never run concurrent editing agents. Independently verify their
  claims. The current user request outranks stale hook or TODO work.

## Before reporting done

- Match proof to claim. Unit, fake, static, or upstream-smoke evidence is not
  integration, end-to-end, or live proof; name the tier and any limitation.
- Prove each gate loads and exercises the target: a gate that has never been
  red is not yet evidence. Break what it guards, watch it fail, restore.
  Classify every unexpected failure or skip; never subtract a red baseline
  from completion evidence.
- Report ship-state separately from code-state. "Done" means a user can do the
  thing; a green build on a feature nobody can reach is a green build.
- Run the relevant checks (`make check`, targeted tests) and report only
  observed results. If something could not be verified, say exactly what
  and why.
- Invoke the `reviewer` subagent once after any non-trivial plan or change,
  before handing off. Fix its findings and rerun it at most once.

## Learning

- When a user correction generalizes, update the scoped guidance: this file
  for universal behavior, the matching skill reference for workflow
  behavior. Do not persist one-off preferences.

## Communication

- Be extremely concise. Sacrifice grammar for the sake of concision.
<!-- harness:end -->

## Strido domain rules

Strido is a 3D-printed 12-DoF quadruped (fork of Jerome Graves' Yertle, MIT) that people print, buy, assemble and program from this repository alone. A wrong hole, a colliding link or a swapped pin costs a reprint or a burnt board, so physical claims need machine evidence.

- **Read first:** `README.md`, `requirements/product-requirements.md`, `docs/architecture.md`, `docs/verification.md` (observed evidence), `TODO.md`. Hardware sources of truth live in `hardware/*.yaml`; the CAD is code in `packages/strido-cad`.
- **Skills:** `strido-hardware` (CAD, parts, fits, tolerances), `strido-verification` (evidence tiers Q0–Q3, which gate proves what), `strido-bringup` (electronics, firmware, first power-up), `strido-docs` (docs site, catalogue PDF, renders, 3D viewer), `strido-ntx` (NT-X harness integration).
- **Hardware MCP:** `strido-hardware` server (`.mcp.json`, `uv run --locked strido mcp`) answers part dimensions, fasteners, fits, clearances, pin maps, BOM and verification status from the tracked data and the last verification run. Query it before reading CAD code by hand.
- **Generated, never hand-edited:** `packages/strido-core/src/strido/geometry.py`, `firmware/.../geometry_generated.h`, `ros2/strido_description/{urdf,meshes,config/mass_report.yaml}`, `models/mujoco/*.xml`, `hardware/joint_limits.yaml`, `hardware/print/{stl,plates,print_list.md}`, `docs/bom/*`, `docs/assembly/*`, `docs/verification/*.md`, `docs/catalog/*`, `docs-site/content/{docs,requirements,de}`. Change the source (YAML, CadQuery part, generator) and regenerate with the matching `make` target; `make drift` fails on stale bindings.
- **German site:** every published English page has a translation catalogue in `i18n/de/` (`i18n/README.md`: workflow, style, terms that stay English). After changing English docs or regenerating pages run `make i18n` and translate the new `"de": null` entries; `make drift` fails until they are translated.
- **Physical changes:** any change to a part, placement, fastener or pose must pass `make verify` (interference, ROM, fits/tolerances, moving clearance, sensor FoV) and `make bom` (every CAD part and fastener purchasable). Never widen an allowed-contact rule or a tolerance band to make a check pass; fix the geometry or record the decision in `docs/decisions.md`.
- **Electronics:** pins, addresses, channels and ratings come from `hardware/electronics.yaml`; firmware `board_config.h` must match (`make drift`). Unknown hardware facts (servo response, real current draw) stay marked `[ESTIMATE]`/`[UNVERIFIED]` until measured on a built robot.
- **Evidence:** CAD, simulation and native firmware tests are not hardware evidence. Record what ran, its tier and its boundary in `docs/verification.md`; a new gate must be seen red once.
- **Upstream:** `upstream/yertle/` is the unmodified upstream design and code (reference only); Strido derivatives live in `packages/`, `hardware/`, `firmware/`, `ros2/`.
- **NT-X boundary:** `packages/strido-ntx` is the only code that knows the NT-X harness; never edit `../../ntx-harness` from this repository.
- **Commands:** `make setup`, `make check-fast` (Q0), `make verify`, `make check` (Q1), `make smoke` (Q2), `make publish`, `make docs`, `make firmware`, `make sim-walk`, `make rl-smoke`, `make ntx-smoke`. Runbook: `docs/harness.md`.
