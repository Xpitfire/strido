---
name: strido-ntx
description: Use when integrating Strido with the NT-X robotics harness and Studio - the strido-ntx extension (catalog robot spec, MJCF, stand skill), the serial RobotPort and its semantics, the registry adapter, the integration smoke and the NT-X core change needed for live hardware sessions.
---

# NT-X integration

## Read before deciding
- `docs/ntx-integration.md` (what works, port semantics, the open NT-X core change)
- `packages/strido-ntx/src/strido_ntx/` (`codec.py` pure mapping, `serial_port.py` RobotPort, `plugin.py` registry,
  `build_assets.py` generator, `smoke_inner.py` checks run inside NT-X)
- NT-X contracts (read-only): `../../ntx-harness/src/ntx/core/{contracts.py,ports.py,registry.py}`

## Rules
- Never edit `../../ntx-harness` from this repository. Needed NT-X changes go to `docs/ntx-integration.md` and `TODO.md`.
- The catalog assets are generated: `python -m strido_ntx.build_assets` (runs in `make models`); `make drift` checks them.
- Keep the codec free of NT-X imports (testable here); only `serial_port.py`, `plugin.py`, `smoke_inner.py` import `ntx`.
- Port semantics are explicit: commanded q (no feedback), no odometry, latched e-stop = servos limp. Do not fake
  measurements NT-X would trust.

## Proof
`make ntx-smoke` (NT-X env via `uv run --project ../../ntx-harness --with-editable …`, NT-X venv untouched):
catalog load, 2 s stand in NT-X MuJoCo, registry adapter, port against the protocol-level fake MCU.
`tests/ntx/` cover the codec here.
