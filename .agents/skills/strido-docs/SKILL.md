---
name: strido-docs
description: Use when changing Strido documentation or published artefacts - the VitePress site (docs-site), the parts catalogue and A4 assembly book PDF, the IKEA-style manual, renders with the LCD face, and the web 3D viewer (GLB). Covers which files are authored vs generated and how to regenerate and check them.
---

# Documentation and published artefacts

## Authored vs generated
| Authored (edit) | Generated (never edit; regenerate) |
|---|---|
| `docs/*.md` (overview, getting-started, architecture, decisions, electronics, design, software, simulation, ntx-integration, harness, configuration, verification) | `docs/bom/*` (`make bom`), `docs/assembly/*` (`make manual`), `docs/catalog/*` (`make catalog`), `docs/viewer/*` (`make viewer`), `docs/images/*` (`make renders`), `docs/verification/*.md` + `data/` (`make verify`), `hardware/print/*` (`make print`) |
| `requirements/product-requirements.md` | `docs-site/content/{docs,requirements,public/*}` (sync script) |
| `docs-site/content/index.md`, `.vitepress/{config.mts,theme/}` | |
| `packages/strido-publish/src/strido_publish/templates/book.{html.j2,css}` | |

## Commands
- `make publish` (print, bom, manual, renders, viewer, catalog) — Blender ≥ 4 and Pango required.
- `make docs` (dev server :4173), `make docs-build` (fails on dead links).
- Look at the output: open the PDF pages and the site (viewer loads, catalogue cards render, mermaid diagrams draw).
  A build that passes with an empty viewer is a bug.

## Rules
- Every document starts with a `> **Status:**` line saying what it proves.
- Links to repository files outside `docs/` are rewritten to GitHub by the site; keep them relative.
- The book draws fasteners in true millimetres: never scale its SVGs.
- New pages: add them to `SECTIONS` in `docs-site/scripts/sync-docs.mjs`.
