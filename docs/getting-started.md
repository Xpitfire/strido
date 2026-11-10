# Getting started

Seven stages from an empty desk to a walking robot. Each stage links to the page with the details; the [Learn wiki](wiki/README.md) explains the engineering behind them.

## 1 · Print

Easiest: the [print kit](print-kit.md) page builds a ready-to-print package (pick complete robots or single parts; STLs named with their quantity, the slicer profile, a parts sheet and the ready plates), or take the whole build kit from the [downloads](downloads.md) page. Import the included `prusaslicer.ini` (PrusaSlicer: File › Import › Import Config; other slicers: enter the values from the [print list](../hardware/print/print_list.md)), then print the plates (220 × 220 mm bed or larger) or the single STLs. Every part and plate was sliced with exactly this profile ([printability](verification/printability.md)); about 1.0 kg PETG and 100 h of printing. Lime parts are the shells and shoulders; everything else graphite. After printing, follow the warnings in the [fit report](verification/fits.md).

## 2 · Buy

The [shop](shop.md) sells the complete robot as one kit (or single parts) with real shop offers: pick one of the four [buying plans](bom/shopping_list.md) or change the shop per part, see the total with every shop's shipping in the cart, and check out per shop with a guided checklist that opens each item's shop page in turn (plus a copyable order list for shops with a quick-order form). Fasteners include 10 % spares. Tools: section E of the [catalogue PDF](catalog/strido-catalog.pdf).

## 3 · Assemble

Follow the [assembly manual](assembly/README.md) or the PDF. The [3D viewer](viewer.md) replays every step on the full model. Before step 1: centre all twelve servos (step 5 below can be done on the bench first).

## 4 · Wire

[Electronics](electronics.md): power tree, wiring list, the routed wiring harness, pin map and the first smoke test without servos. The pin map is machine-checked against the firmware ([electronics check](verification/electronics.md)).

## 5 · Flash and calibrate

```bash
uv sync --locked                                   # Python tools (strido-cli)
cd firmware/strido_esp32s3 && pio run -e xiao_esp32s3 -t upload
uv run strido-cli --port /dev/ttyACM0 center      # assembly reference: hip vertical, femur 45° back, crank 35°
uv run strido-cli --port /dev/ttyACM0 calibrate   # per-joint trim, stored in flash
```

Details: [software › firmware](software.md#firmware) and [electronics › wiring harness](electronics.md#wiring-harness).

## 6 · Run

On the Raspberry Pi 5 (Docker): `docker compose -f docker/compose.yaml run --rm robot`, then `ros2 run teleop_twist_keyboard teleop_twist_keyboard`. Topics and launch files: [software](software.md).

## 7 · Simulate, train, integrate

`make sim-walk`, `make sim-gazebo`, `make rl-train`, and the NT-X harness via `make ntx-smoke`: [simulation](simulation.md), [NT-X integration](ntx-integration.md).

## Developing on this repository

Changing the design, running the verification gates or rebuilding this site: see the [harness runbook](harness.md).
