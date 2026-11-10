---
name: strido-verification
description: Use when proving a Strido change works - choosing the evidence tier (Q0 static/unit, Q1 CAD verification, Q2 simulation and integration smokes, Q3 hardware), running the matching make targets, breaking each new gate once, and recording observed results in docs/verification.md.
---

# Proving a Strido change

CAD, simulation and native firmware tests are not hardware evidence. State the tier with every claim.

## Tiers
| Tier | Command | Proves | Time |
|---|---|---|---|
| Q0 | `make check-fast` | lint, strict types (core/ntx/workspace), import layers, drift of generated bindings/reports/NT-X assets, Python tests + coverage, firmware native tests | ~1 min |
| Q1 | `make verify` | interference (4 poses), ROM sweep, fits/tolerances (every screw, every bearing seat), moving clearance (13 poses), sensor FoV | ~10 min |
| Q1 | `make printability` | every printed part and 3MF plate sliced by PrusaSlicer with the kit profile (no errors, no stability warnings), wall-thickness scan, filament/time | ~1 min (needs PrusaSlicer) |
| Q1 | `make check` | Q0 + Q1 + printability + BOM coverage + CAD tests + docs build + harness checks | ~13 min |
| Q2 | `make smoke` | MuJoCo walk video, MCP server over stdio, NT-X extension inside the NT-X harness | ~2 min |
| Q2 | `make sim-gazebo`, `make rl-smoke` | ROS 2 + Gazebo walk in Docker; PPO pipeline | 5–10 min |
| Q3 | built robot | stand, walk, measured current/runtime/servo response | — |

## Break each new gate once
Break what the gate guards (e.g. move a hole, swap a pin in `board_config.h`, shorten a pilot), run the gate,
see it red, restore, see it green. Record both commands and outcomes.

## Reports to read, not just exit codes
`docs/verification/fits.md` (warnings = actions for the builder), `clearance.md` (tight pairs),
`interference.md` (classified overlaps), `sensors.md`, `electronics.md` (incl. voltage domains: "pass, no margin"
rows), `printability.md`. A green gate with a surprising report is a bug.

## Record evidence
Append a dated section to `docs/verification.md`: commit, tier, exact command, observed counts/exit codes,
evidence boundary. Never paste results you did not observe; mark inferences `[INFERENCE]`.
