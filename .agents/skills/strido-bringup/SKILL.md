---
name: strido-bringup
description: Use for Strido electronics, firmware and first power-up - pins, I²C addresses, servo channels, power budget, wiring, flashing the XIAO ESP32-S3, servo calibration with strido-cli, the MCU wire protocol and the ROS 2 bringup on the Raspberry Pi 5.
---

# Electronics, firmware and bring-up

A swapped pin or an undersized wire burns a board. The YAML, the firmware header and the docs must agree,
and `make drift` proves it.

## Read before deciding
- `hardware/electronics.yaml` (single source: pins, buses, channels, ratings, wires)
- `docs/electronics.md` (power tree, wiring list, harness steps, XT60 contact rule, safety)
- `docs/verification/electronics.md` (generated check report), `docs/software.md` (protocol, topics)

## Rules
- Pins/addresses/channels change in `hardware/electronics.yaml` **and** `firmware/strido_esp32s3/src/board_config.h`
  together; `python -m strido_verify.electronics` must pass (it is part of `make drift`).
- The wire protocol has two mirrors: `packages/strido-core/src/strido/protocol.py` and `firmware/.../protocol.{h,cpp}`.
  Change both; the firmware native tests use Python golden values.
- Joint geometry in firmware is generated (`geometry_generated.h`): change the CAD/limits, run `make cad`.
- Servo power never passes through a logic board; UBECs at 6.0 V (jumper open), never 7.4 V.
- Unknown hardware facts (current draw, servo response) stay `[ESTIMATE]`/`[UNVERIFIED]` until measured.

## Commands
- Firmware: `make test-firmware` (native), `make firmware` (build), `cd firmware/strido_esp32s3 && pio run -t upload`.
- Bench: `uv run strido-cli --port <dev> center | pulse FL_thigh 1600 | calibrate | monitor`.
- Pi: `docker compose -f docker/compose.yaml build ros`, `… run --rm robot`; simulation test `make sim-gazebo`.
