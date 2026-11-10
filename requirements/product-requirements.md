# Product requirements

> **Status:** requirement catalogue for Strido 0.2. The *Status* column states what the repository demonstrates today; evidence tiers are defined in [docs/verification.md](../docs/verification.md). CAD, simulation and native tests are not hardware evidence.

Strido is a small, affordable, 3D-printed quadruped that a developer builds at home to develop ROS 2 and learning software that later transfers to a Unitree Go2 at work, and that runs in the NT-X harness. It reuses the proven Yertle legs and frame and adds what a Mini Pupper 4 class robot offers: a face display, a 360° LiDAR, a wide camera and an onboard computer.

## Families

| Family | Scope |
|---|---|
| MECH | Mechanical design, fits, motion |
| MAKE | Printing, purchasing, assembly documentation |
| ELEC | Power, wiring, pins |
| FW | Motion-controller firmware |
| SW | Robot software (ROS 2, bench tools) |
| SIM | Simulation and learning |
| NTX | NT-X harness integration |
| DOC | Documentation site, catalogue, renders |
| ENG | Engineering harness, checks, release |

## Requirements

| ID | Requirement and observable acceptance | Prio | Status | Evidence |
|---|---|---|---|---|
| MECH-001 | 12 actuated joints (hip abduction, thigh, knee per leg) in Go2 joint naming and order. | MUST | met (Q1) | `models/mujoco/strido.xml`, `hardware/joint_limits.yaml` |
| MECH-002 | No two solids of the assembled robot intersect except designed contacts (threads, seats, press fits), in every reference pose. | MUST | met (Q1) | [interference](../docs/verification/interference.md) |
| MECH-003 | Every screw passes through clearance holes or forms its thread in a pilot of 0.70–0.97 d (printed size), is held by a nut, pilot or threaded part, and engages ≥ 1.0 d; every bearing seat is within −0.15…+0.30 mm of the bearing OD. | MUST | met (Q1) | [fits](../docs/verification/fits.md) |
| MECH-004 | Parts on different rigid bodies keep ≥ 0.3 mm running clearance in every operating pose (stand/crouch/tall, trot cycle, hip limits). | MUST | met (Q1) | [clearance](../docs/verification/clearance.md) |
| MECH-005 | Joint limits come from a collision and linkage sweep (incl. the mirrored partner leg and 0.3 mm clearance) and are enforced identically in firmware, Python and simulation. | MUST | met (Q0/Q1) | `make drift`, `hardware/joint_limits.yaml` |
| MECH-006 | Sensor head: 2" LCD face, 360° LiDAR with an unobstructed scan plane, wide camera that does not see the robot. | MUST | met (Q1) | [sensors](../docs/verification/sensors.md) |
| MAKE-001 | Every printed part ships as an oriented STL and on 220 × 220 mm 3MF plates that fit a 220 × 220 × 250 mm bed; closed manifold. | MUST | met (Q1) | `hardware/print/` |
| MAKE-002 | The BOM covers every purchased part and fastener of the CAD (fasteners + 10 %, ≥ 2 spares) in every shopping strategy; offers cite a vendor, SKU, price and date. | MUST | met (Q1) | `make bom`, [BOM](../docs/bom/README.md) |
| MAKE-003 | Shopping plan minimises the delivered cost (shipping thresholds, per-order fees) and offers fewest-shops, EU-only and genuine-board alternatives. | SHOULD | met (Q1) | [shopping list](../docs/bom/shopping_list.md) |
| MAKE-004 | IKEA-style assembly: every printed part, purchased part and fastener appears in exactly one step's parts box, with a CAD drawing per step. | MUST | met (Q1) | [assembly](../docs/assembly/README.md) |
| MAKE-005 | A4 catalogue & assembly book (PDF): printed and purchased part catalogues, fasteners at 1:1, shopping plan, tools, all steps, wiring, software appendix. | MUST | met (Q1) | [catalogue PDF](../docs/catalog/strido-catalog.pdf) |
| ELEC-001 | Servo current never flows through a logic board; separate fused servo (6.0 V) and logic (5 V) domains with a physical arming key. | MUST | met (design) | [electronics](../docs/electronics.md) |
| ELEC-002 | Pins, I²C addresses, servo channels, fuses and wire gauges are machine-checked against the firmware header and the load. | MUST | met (Q0) | [electronics check](../docs/verification/electronics.md) |
| FW-001 | Command watchdog (hold 200 ms, relax 2 s), latched e-stop via PCA9685 OE, low-battery cut-off, refusal to drive without the power monitor. | MUST | met (Q0 native) | `make test-firmware` |
| FW-002 | Joint ↔ servo mapping is linkage-exact (knee driven through the crank four-bar) and identical to the Python mirror. | MUST | met (Q0) | firmware tests with Python golden values |
| SW-001 | ROS 2 Jazzy bringup with a Go2-style contract: `/cmd_vel`, `/joint_states`, `/imu/data`, `/scan`, `/battery_state`, `/tf`. | MUST | met (Q2 sim) | `make sim-gazebo` |
| SW-002 | Bench CLI to centre, pulse, calibrate and monitor the servos without ROS. | MUST | met (Q0) | `tests/core/test_cli.py` |
| SIM-001 | MuJoCo and Gazebo models generated from the verified CAD (masses, inertias, limits). | MUST | met (Q2) | `make models`, `make sim-walk` |
| SIM-002 | A velocity-tracking policy trained in simulation runs through the same numpy runtime as on the robot. | SHOULD | partial (sim only) | `make rl-smoke`, `models/policies/ppo-v1` |
| NTX-001 | The robot appears in the NT-X catalog (robot spec + MJCF + stand skill) without NT-X core changes, and stands in NT-X MuJoCo. | MUST | met (Q2) | `make ntx-smoke` |
| NTX-002 | A `RobotPort` drives the real robot over the MCU protocol with explicit semantics (no odometry, commanded q, latched protective stop). | MUST | met (protocol-level fake MCU) | `make ntx-smoke`, `tests/ntx/` |
| NTX-003 | NT-X sessions open the Strido port through the registry. | SHOULD | open: NT-X core dispatches hardware only to Unitree SDK2 | [NT-X integration](../docs/ntx-integration.md) |
| DOC-001 | Documentation site with the catalogue, an interactive 3D model (explode, step-through, part picking), renders, guides and verification reports. | MUST | met (Q2) | `make docs-build` |
| DOC-002 | Renders of the complete robot including the display face, LiDAR and camera. | MUST | met | `docs/images/` |
| ENG-001 | Engineering harness installed (checks profile) with project skills, a hardware MCP server and gates for lint, types, architecture, drift, tests, firmware and CAD verification. | MUST | met (Q0) | `make check-fast`, `make harness-check` |
| ENG-002 | One command builds a release zip with the full repository, print plates, the PDF, the walk video and the policy. | MUST | met | `make package` |
| HW-001 | A built robot stands, walks under teleoperation, and its measured mass, current and runtime are recorded. | MUST | open: no robot built yet | [TODO](../TODO.md) |
