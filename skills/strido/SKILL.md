---
name: strido
description: Knowledge base of the Strido open quadruped robot (12 servos, Raspberry Pi 5 + ESP32-S3, ROS 2) - parts and shop, printing, assembly steps, electronics and wiring, firmware, simulation, reinforcement learning and the engineering wiki, in English and German. Use when a question concerns building, wiring, programming, simulating or understanding Strido, or the robotics theory its wiki explains.
---

# Strido knowledge base

Answer from the Strido documentation, not from memory: its numbers (prices, lengths, ratings, torques, step numbers) come from the verified CAD and change between releases.

## Where the knowledge is

1. **Bundled references** (if this skill came from `strido-skill.zip`): `references/en/` and `references/de/` hold every page of the site as Markdown; `references/README.md` lists them with their site URLs. Search them with grep (e.g. `grep -ril "fuse" references/en`), then read the matching page.
2. **MCP server `strido`** (`https://strido.cortex.a2olabs.com/mcp` with a Cortex app token, see the site's `docs/ai` page): `search_docs` (ranked sections), `read_page` (a whole page or one section), `list_pages` (the site map), `search_parts` (BOM lines with price, shop and product data). Prefer it over the bundled references: it always serves the deployed version.
3. **Site**: https://strido.cortex.a2olabs.com (Cortex sign-in). `/llms.txt` lists every page; `/llms-full.txt` holds them all. German: `/de/...`.

## Map of the documentation

| Need | Page |
|---|---|
| What the robot is, specs | `docs/overview`, home page |
| First build path | `docs/getting-started` |
| Buy parts, plans, prices | `docs/shop`, `docs/bom/` (BOM), `docs/bom/shopping_list` |
| Print the parts | `docs/print-kit`, `docs/hardware/print-list` |
| Assembly steps (Step 0-23) | `docs/assembly/` (anchors `#step-N`) |
| Power, fuses, wiring list W00-W24, pin map | `docs/electronics` |
| Firmware, ROS 2, Docker | `docs/software` |
| Simulation, training, NT-X | `docs/simulation`, `docs/ntx-integration` |
| Evidence and its limits | `docs/verification` and `docs/verification/*` (clearance, fits, strength, wiring, electronics...) |
| Design decisions | `docs/decisions` (ADR-001...) |
| Theory and background | `docs/wiki/` (theory, hardware, software, making, glossary) |

## How to answer

- Quote the figures and step numbers from the page you read, and give its URL (`https://strido.cortex.a2olabs.com/<route>`, German pages under `/de/`).
- Say which tier a claim has: the verification pages separate CAD checks, simulation and hardware tests; nothing has been verified on a physical robot unless `docs/verification` says so.
- Safety: LiPo handling, fuses and the loop key follow `docs/wiki/making/safety`; never suggest bypassing a fuse or powering servos from the logic supply.
- Answer in the user's language; the German pages carry the same content and the same heading anchors.
