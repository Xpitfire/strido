# Strido: one entry point for CAD, verification, firmware, simulation, docs and release.
# Python runs only through the locked uv workspace (`uv run --locked`); see docs/harness.md.

SHELL := /bin/bash
.DEFAULT_GOAL := help

UV := uv run --locked
PY := $(UV) python
PIO := pio
FIRMWARE := firmware/strido_esp32s3
NTX_HARNESS ?= ../../ntx-harness
VERSION := $(or $(shell git describe --tags --match 'strido-v*' --always --dirty 2>/dev/null | sed 's/^strido-//'),dev)

.PHONY: help setup setup-standalone hooks \
        lint format typecheck layers test test-cad test-firmware test-web drift check-fast check verify printability \
        vendor-cad kinematics rom models cad firmware \
        print bom manual catalog renders viewer publish \
        docs docs-build docs-preview i18n assistant \
        sim-walk sim-gazebo rl-smoke rl-train rl-eval \
        ntx-smoke mcp-smoke smoke harness-check codegraph package clean

help: ## list targets
	@grep -E '^[a-z][a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-17s %s\n", $$1, $$2}'

# ------------------------------------------------------------------ setup
setup-standalone: ## Python workspace + docs-site dependencies (no harness)
	uv sync --locked --all-groups
	npm --prefix docs-site ci

setup: setup-standalone ## full developer setup: submodules, harness, git hooks
	git submodule update --init --recursive
	$(MAKE) -f .harness/Makefile harness-install

# ------------------------------------------------------------------ quality gates
lint: ## ruff lint + format check
	$(UV) ruff check packages src tests ros2
	$(UV) ruff format --check packages src tests ros2

format: ## apply ruff fixes and formatting
	$(UV) ruff check --fix packages src tests ros2
	$(UV) ruff format packages src tests ros2

typecheck: ## mypy (strict for robot runtime, NT-X adapter and workspace tooling)
	$(UV) mypy

layers: ## import-linter architecture contracts
	$(UV) lint-imports

test: ## Python unit/contract tests with coverage gate (no CAD cache needed)
	$(UV) pytest -m "not cad" --cov --cov-report=term

test-cad: ## tests that need the CAD cache (fits, tolerances, catalogue)
	$(UV) pytest -m cad

test-firmware: ## firmware core native unit tests (PlatformIO, host compiler)
	cd $(FIRMWARE) && $(PIO) test -e native

test-web: ## site scripts (translation catalogues) and assistant service unit tests (node:test)
	node --test 'docs-site/scripts/*.test.mjs'
	cd assistant && node --test 'test/*.test.mjs'

drift: ## generated sources are up to date (geometry bindings, pin map, NT-X assets, German translations)
	$(PY) -m strido_cad.codegen --check
	$(PY) -m strido_verify.electronics --check
	$(PY) -m strido_ntx.build_assets --check
	node docs-site/scripts/i18n-catalogues.mjs check

i18n: ## add new or changed English page segments to the German catalogues (i18n/de/), then translate the "de": null entries
	node docs-site/scripts/i18n-catalogues.mjs extract
	node docs-site/scripts/i18n-catalogues.mjs status

check-fast: lint typecheck layers drift test test-firmware test-web ## Q0: everything that runs in seconds to a minute

verify: ## Q1 hardware: hole stacks, fasteners, interference, ROM, fits/tolerances, strength, clearances, wiring, sensor FoV
	$(PY) -m strido_cad.hole_stacks
	$(PY) -m strido_cad.fasteners
	$(PY) -m strido_verify.contacts
	$(PY) -m strido_verify.sensor_fov
	$(PY) -m strido_verify.rom
	$(PY) -m strido_verify.fits
	$(PY) -m strido_verify.strength
	$(PY) -m strido_verify.clearance
	$(PY) -m strido_verify.wiring
	$(PY) -m strido_cad.codegen --check

printability: print ## slice every printed part and 3MF plate with PrusaSlicer + wall-thickness scan (needs PrusaSlicer)
	$(PY) -m strido_verify.printability

check: check-fast verify printability bom test-cad docs-build harness-check ## Q1: full local gate (CAD verification ~10 min)

# ------------------------------------------------------------------ CAD
vendor-cad: ## download pinned vendor STEP models into build/vendor_cad (not redistributed)
	$(PY) -m strido_cad.fetch_vendor_cad

# codegen runs before the sweep (new link lengths) and after it (new limits)
kinematics: ## measure kinematics from the upstream STEP, sweep ROM, regenerate bindings
	$(PY) -m strido_cad.extract_kinematics
	$(PY) -m strido_cad.codegen
	$(PY) -m strido_verify.rom
	$(PY) -m strido_cad.codegen

rom: ## range-of-motion sweep -> hardware/joint_limits.yaml
	$(PY) -m strido_verify.rom

models: ## URDF/xacro, MJCF, meshes and mass report from the CAD; NT-X assets
	$(PY) -m strido_cad.models
	$(PY) -m strido_ntx.build_assets

cad: kinematics models ## kinematics + models

firmware: ## build the XIAO ESP32-S3 firmware
	cd $(FIRMWARE) && $(PIO) run -e xiao_esp32s3

# ------------------------------------------------------------------ publication
print: ## print kit: oriented STLs, 3MF plates, print list
	$(PY) -m strido_publish.print_files

bom: ## BOM, CAD coverage check, shopping bundles
	$(PY) -m strido_publish.bom

manual: ## assembly step drawings + Markdown manual (Blender)
	$(PY) -m strido_publish.manual

catalog: ## (after print, manual, renders) parts catalogue JSON + A4 catalogue & assembly book PDF (WeasyPrint)
	$(PY) -m strido_publish.book

renders: ## hero, front, rear, exploded, section and x-ray renders (Blender)
	$(PY) -m strido_publish.renders

viewer: ## GLB assembly + step/explode metadata for the web 3D viewer
	$(PY) -m strido_publish.viewer

publish: ## regenerate every published artefact (in order: the book reads print, manual and renders output)
	$(MAKE) print
	$(MAKE) bom
	$(MAKE) manual
	$(MAKE) renders
	$(MAKE) viewer
	$(MAKE) catalog

# ------------------------------------------------------------------ documentation site
docs: ## docs site dev server on http://127.0.0.1:4173
	npm --prefix docs-site run dev

docs-build: ## static docs site build (fails on dead links)
	npm --prefix docs-site run build

docs-preview: ## serve the built site
	npm --prefix docs-site run preview

assistant: ## AI assistant on http://127.0.0.1:8090 for `make docs` (development identity; model via ~/.config/cortex/keyring.prod.env)
	npm --prefix docs-site run sync
	set -a; . $(HOME)/.config/cortex/keyring.prod.env; set +a; \
	  cd assistant && HOST=127.0.0.1 ASSISTANT_AUTH_MODE=dev ASSISTANT_DEV=1 KNOWLEDGE_DIR=../docs-site/content ASSISTANT_DATA_DIR=../build/assistant node src/server.mjs

# ------------------------------------------------------------------ simulation and learning
sim-walk: ## MuJoCo trot demo video -> build/sim/walk.mp4
	$(PY) -m strido_sim.walk --seconds 10 --vx 0.15 --video build/sim/walk.mp4

sim-gazebo: ## headless Gazebo walk test in Docker (ROS 2 Jazzy); POLICY=<policy.npz> tests the learned policy
	docker compose -f docker/compose.yaml build ros
ifdef POLICY
	docker compose -f docker/compose.yaml run --rm -v $(abspath $(POLICY)):/policy.npz:ro -e POLICY=/policy.npz sim-smoke
else
	docker compose -f docker/compose.yaml run --rm sim-smoke
endif

rl-smoke: ## 20k-step PPO run + evaluation (pipeline check)
	$(UV) --group rl python -m strido_sim.rl.train --smoke --run smoke
	$(UV) --group rl python -m strido_sim.rl.evaluate build/rl/smoke/policy.npz --seconds 3

rl-train: ## full PPO training (20 M steps, 8 envs)
	$(UV) --group rl python -m strido_sim.rl.train --timesteps 20000000 --envs 8 --run ppo-v1

rl-eval: ## evaluate the released policy with a video
	$(UV) --group rl python -m strido_sim.rl.evaluate models/policies/ppo-v1/policy.npz --seconds 10 --video build/rl/eval.mp4

# ------------------------------------------------------------------ integration smokes
ntx-smoke: ## load the Strido extension inside the NT-X harness (needs ../../ntx-harness)
	$(PY) -m strido_ntx.smoke --ntx-harness $(NTX_HARNESS)

mcp-smoke: ## start the hardware MCP server over stdio and call every tool
	$(PY) -m strido_workspace.mcp_smoke

smoke: sim-walk mcp-smoke ntx-smoke ## Q2: runtime smokes that need no hardware

# ------------------------------------------------------------------ harness
harness-check: ## imported harness self-tests + drift + checks pack
	env -u AGENT_GIT_GUARD -u AGENT_PY_GUARD -u AGENT_TERSE_GUARD $(MAKE) -f .harness/Makefile harness-check-imported
	$(MAKE) -f .harness/Makefile harness-checks

codegraph: ## build or sync the CodeGraph index
	$(MAKE) -f .harness/Makefile harness-codegraph

# ------------------------------------------------------------------ release
package: ## release zip in dist/: full repository (print kit, book PDF, policy) + the simulation video
	rm -rf dist/strido-$(VERSION) && mkdir -p dist/strido-$(VERSION)
	git archive --format=tar HEAD | tar -x -C dist/strido-$(VERSION)
	mkdir -p dist/strido-$(VERSION)/release
	cp build/sim/walk.mp4 dist/strido-$(VERSION)/release/
	cd dist && rm -f strido-$(VERSION).zip && zip -qr strido-$(VERSION).zip strido-$(VERSION)
	@echo "dist/strido-$(VERSION).zip"

clean: ## remove generated, untracked output
	rm -rf build/render build/print dist docs-site/content/.vitepress/dist
