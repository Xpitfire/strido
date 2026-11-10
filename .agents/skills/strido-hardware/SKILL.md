---
name: strido-hardware
description: Use when changing or reasoning about Strido mechanics - printed parts, placements, fasteners, bearings, joint limits, fits, tolerances, clearances, print files or the BOM. Covers where the CAD lives, how to query part facts through the strido-hardware MCP server, and which gates must pass before a physical change is done.
---

# Changing Strido hardware

People print and assemble from this repository alone. Every physical claim must come from the CAD
and pass a gate; a plausible number is a reprint waiting to happen.

## Read before deciding
- `docs/design.md` (CAD pipeline, frames, changes vs upstream), `docs/architecture.md`
- `hardware/*.yaml` (sources of truth), `hardware/verification/tolerances.yaml`, `allowed_contacts.yaml`
- `hardware/assembly/corrections.yaml` (why some upstream parts are re-placed)
- Reports: `docs/verification/{interference,fits,clearance,sensors}.md`

## Ask the MCP server first
`strido-hardware` (stdio, `.mcp.json`): `get_part`, `list_parts`, `get_fastener`, `fits`, `clearances`,
`measure_gap` (exact distance in a pose; loads the CAD), `joint_limits`, `bom_line`, `verification_status`.
CLI equivalent: `uv run strido part <id>`, `strido fits --status warn`, `strido clearances --max-gap 1`.

## Where things are
| Change | Edit | Then |
|---|---|---|
| New/modified printed part | `packages/strido-cad/src/strido_cad/parts.py` (CadQuery booleans on upstream geometry, STEP frame mm) | `make verify`, `make print` |
| Purchased part model | `strido_cad/vendor.py` (official STEP when fetched, datasheet envelope otherwise) | `make verify`, `make bom` |
| Upstream fastener rule | `hardware/fasteners_upstream.yaml` (matched to measured hole stacks; counts gated) | `make verify` |
| Fastener catalogue | `hardware/fasteners.yaml` | `make bom` |
| Re-place an upstream part | `hardware/assembly/corrections.yaml` (rotation about a measured leg axis, per body) | `make verify` |
| Re-drill an upstream part | `DERIVED_PILOTS` in `strido_cad/catalog.py` (variant per instance, own print file) | `make verify`, `make print` |
| Joint limits | never by hand: `make rom` (collision + mirrored partner + 0.3 mm clearance) then `make cad` | `make drift` |

## Rules
- Frames: STEP mm, +x robot left, +y robot rear, +z up; `assembly.step_to_base()` gives REP-103.
- Never widen a tolerance band or add an allowed-contact rule to make a check pass. Fix the geometry; if a rule
  really must change, write an ADR in `docs/decisions.md` with the physical reason.
- Upstream files in `upstream/yertle/` stay byte-identical; fixes are derived parts or corrections.
- A printed hole is ~0.15 mm undersize: clearance holes ≥ d + 0.2 (CAD), self-tapping pilots 0.7–0.9 d (printed).
- After any change: `make verify` (all green), `make bom` (coverage), `make publish` (print kit, manual, renders,
  viewer, book), record the run in `docs/verification.md`.
