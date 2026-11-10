# Strido work tracker

## Pending

- [ ] Physical build: print, assemble and wire a first robot; record measured mass, standing current and runtime against the CAD/estimate values in `docs/electronics.md` and `docs/design.md` (HW-001).
- [ ] Hardware bring-up: flash firmware, run `strido-cli calibrate`, verify servo directions and the linkage-exact knee mapping on the real leg; check the right-leg horn orientation (`hardware/assembly/corrections.yaml`: disc horn −30°, connector +22°) and the new front servo-mount pilots on printed parts.
- [ ] Print-test the fit warnings of `docs/verification/fits.md` (drill sizes, weak self-tapping pilots in upstream parts) and tune `hardware/verification/tolerances.yaml` `expected_hole_shrink_mm` to a measured printer.
- [ ] NT-X core change for live hardware sessions: registry-based `open_robot_port` / `transport.kind` (NT-X repository, see `docs/ntx-integration.md`), then add a `strido-desk` target with qualification gates (NTX-003).
- [ ] Confirm on hardware: ONPOW GQ12B body depth (≤ 27.5 mm behind the panel), RPLIDAR USB adapter size (CAD uses a 32 × 22 × 10 mm envelope), Pi 5 `gpio-poweroff` driving the Pololu OFF input.
- [ ] Measure servo response (kp/kv, latency) and retrain the PPO policy with it; improve lateral (0.023 m/s for 0.1 m/s) and reverse tracking; consider a base-velocity estimate in the observation.
- [ ] Bridge NT-X `locomotion-velocity` policies and the Strido feedback-free policy runtime (one observation layout or an adapter).
- [ ] Camera on ROS 2: build `camera_ros` against the Raspberry Pi libcamera fork on the robot (not in the Docker image).
- [ ] Measure the PCA9685 OE voltage with the XIAO held in reset/bootloader (must be ≥ 2.4 V with the 2.2 kΩ pull-up).
- [ ] Consider a different connector family for the arming port and loop key (EC3/XT30) so the pack can never mate with the arming port.
- [ ] Optional: official CAD for the WAGO 221-415 and SPT5435LV (datasheet envelopes today); widen the four 0.73–0.79 mm moving clearances at the hip-out limit (shoulders vs back shell, arm horns vs front shell).
- [ ] Print-test the ADR-009 servo-mount M3 pilots (with and without -0.15 mm X-Y hole compensation); if a thread strips, add Ø2.5 mm re-pilot variants.
- [ ] First test prints with `hardware/print/prusaslicer.ini`: confirm the slicer-verified kit on a real printer (deck supports under the IMU pocket, the thin-wall warnings in `docs/verification/printability.md`, XT60 fit in the bezel), then measure the hole shrink for `tolerances.yaml`.
- [ ] Measure the XIAO 3V3 rail under load (servo PWM and LCD run at 3.3 V without margin) and each UBEC's unloaded output (accept 5.8–6.0 V).
- [ ] Print-test the CA-hardened pilot fallback on a weak M3 pilot (ADR-009) and record the result.
- [ ] Measure a real landing (IMU peak or a force plate) to replace the assumed 3 × weight impact factor in `hardware/strength.yaml`.
- [ ] Spot-check the remaining product specs written from memory in `hardware/products.yaml` (all specs checked by the research pass were correct).
- [ ] Measure on the first build: the SPT5435LV lead exit (CAD assumes the grommet at the shaft end, 5 mm above the bottom), the pack lead and UBEC lead lengths, the RPLIDAR sensor-to-adapter cable; then re-run `make verify` (the front knee leads have only 12 mm to spare).
- [ ] Consider a compact fused battery input under the deck (fuse within a few cm of the XT60) so W01 is no longer unfused (ADR-011).

- [ ] Shared Keyring key for the assistant: today `.cortex/app.yml` names the owner as Keyring subscriber, so only the owner's account can use the AI bar; once the pool can serve every signed-in user, drop `subscriber` (ADR-012).
- [ ] `cortex apps connect strido` (MCP + skill in one step) needs Control to record `.cortex/package.json`; today it records packages only for Cortex-created apps, so agents add the MCP server with a token from `cortex api post /api/v1/apps/strido/tokens` (`docs/ai.md`).
- [ ] Copy only `CORTEX_APP_HEADER_SECRET` into the host workspace `.env` instead of loading the gateway's generated env file into the assistant (ADR-012, the Canvas contract).
- [ ] First print of `stiff_long_link`: press the sleeve pairs, check the link turns freely over the whole knee range on a built leg (CAD: ≥ 1 mm to every neighbour).

## Completed

- [x] 2026-11-01 Builder review, round 2: servo mounts printed like a U, `inner_tibia` on its flat side, hole overhang trick cut into every hole step (tibia and outer shoulder frame bearing seats; tibias need a support blocker in the bore).
- [x] 2026-11-01 Stiff Strido long link (`stiff_long_link`, ADR-010 resolved: buckling S 0.34 → 2.53, joint limits unchanged) and print kit re-oriented (femur, top bracket, femur servo connector, side beam, right shoulder, camera base; servo mounts kept upright for their pilots), after a builder's review of the 3MF plates.
- [x] 2026-10-31 German site under `/de/` from translation catalogues (`i18n/de/`, drift-checked), AI assistant bar (floating, pinned sidebar, history, image/text attachments) with the `assistant/` service on Cortex Keyring, MCP server + Agent Skill + `llms.txt` for agents (ADR-012).
- [x] 2026-10-31 Wiring harness routed and checked in the CAD (ADR-011): `hardware/wiring.yaml`, router, cables/sleeves/ties/mounts in renders, viewer, manual (Steps 14–16, 20) and masses; wiring gate (174 checks) in `make verify`; fixed fuse-holder lead room, IMU/XIAO connector fit, STEMMA and 18 AWG counts, LiDAR adapter over the slot, 18 AWG tap behind the main fuse; servo extensions dropped; Learn article on cable management.
- [x] 2026-10-31 LaTeX math on the docs site; Learn wiki "Robotics theory" (7 articles) and theory added to the existing pages; strength report typeset.
- [x] 2026-10-31 Strength gate (bending, buckling, screw shear, hole pressure, bearings, pilot torques) with ADR-010; guided per-shop checkout replacing the dead Amazon cart link; offer variants; datasheet corrections (UBEC 15 A, LiPo 60C, PETG filament offers); mobile layout pass.
- [x] 2026-10-31 Docs site: parts shop (kit product, cart, per-shop checkout with one-click Amazon cart), print kit builder (ready-to-print ZIP), product pages for every part (`hardware/products.yaml`), Learn wiki with 18 articles and glossary, nav cart, assembly progress, site audit (35 findings) fixed; thread-locker-on-PETG guidance replaced by CA-hardened pilots.
- [x] 2026-10-31 Documentation site deployed via Cortex at https://strido.cortex.a2olabs.com/ (SSO) with a Downloads page: build kit ZIP (all STLs, 13 plates, slicer profile, print list, book PDF, BOM), book PDF, 3D model; repository linked, kept private.
- [x] 2026-10-31 Printability gate (PrusaSlicer slice of every part and plate + wall-thickness scan) and electronics voltage-domain checks; fixed deck supports, plate spacing, XT60 window reliefs, UBEC acceptance window.
- [x] 2026-10-31 `make sim-gazebo` on the v0.2 layout: 0.98 m in 8 s at 0.15 m/s, upright, all sensor topics publishing.
- [x] 2026-10-31 Review fixes: NT-X port accepts real `pd-pose` output and fails closed on IMU loss; fit band restored to 0.93 d with ADR-009 accepted upstream pilots; engagement/seat/clearance-exemption gates tightened; CAD cache digest covers all inputs; book verification page computed from reports; face matches firmware.
- [x] 2026-10-31 v0.2.0 rework: engineering harness (`.harness`, checks profile), project AGENTS rules, five project skills, `strido-hardware` MCP server and `strido` CLI.
- [x] 2026-10-31 uv workspace with layered packages (`strido-core`, `-cad`, `-verify`, `-publish`, `-sim`, `-ntx`, workspace), import-linter contracts, strict mypy for runtime code, coverage gate, CI workflow; upstream Yertle moved to `upstream/yertle/`.
- [x] 2026-10-31 New gates: fits and tolerances (every screw and bearing seat), moving-part clearance over 13 poses, electronics consistency (pins/addresses/channels/fuses/wires vs firmware), print-kit completeness; ROM sweep with the mirrored partner leg and 0.3 mm clearance.
- [x] 2026-10-31 Defects fixed: LiDAR pedestal pilot depth, front servo-mount hip pivot pilot (new print variants), right-leg femur horn/connector pattern, left thigh horn screw direction, feet collision at the inward hip limits, camera parts missing from the 3MF plates.
- [x] 2026-10-31 Documentation: VitePress site (parts catalogue, interactive 3D viewer with explode/step/pick, mermaid diagrams), A4 catalogue & assembly book PDF (fasteners at 1:1), renders with the LCD face, requirements catalogue, architecture, ADRs, harness runbook.
- [x] 2026-10-31 NT-X extension (`strido-ntx`): generated robot spec + MJCF + stand skill, serial `RobotPort`, registry adapter; verified inside the NT-X harness (`make ntx-smoke`).
- [x] 2026-10-30 v0.1.0: forked Yertle, CAD pipeline, verified assembly, Strido parts, electronics, firmware, ROS 2, MuJoCo/Gazebo, PPO, BOM optimiser, IKEA-style manual, renders, release `strido-v0.1.0`.
