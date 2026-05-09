# AGENTS.md

Root entry contract for Codex in Meta_workflow. Keep this file light: it routes agents to the right subsystem docs and records hard boundaries only.

## Project

Meta_workflow is a meta workflow engine for guiding arbitrary projects through business workflow design, execution, validation, memory, recall, and evolution.

## Read First

1. `README.md` for repository map and current focus.
2. `docs/architecture/vision.md` for product direction and engine shape.
3. `docs/methodology/map_methodology.md` for the MAP paper methodology used by this project.
4. `integrations/pro_bridge/README.md` before any Pro/external expert work.

## Routing

- Pro review or external expert handoff: use `integrations/pro_bridge/`.
- First architecture review with Pro: use `docs/pro_handoffs/first_architecture_review.md`.
- Methodology questions about the paper: use `docs/methodology/map_methodology.md` and `references/papers/s41467-025-63804-5.pdf`.
- Architecture planning: update docs under `docs/architecture/`.
- Runtime state, captures, local configs, and local registries stay out of Git.

## Hard Boundaries

- Pro is external advice, not project truth.
- Do not let Pro responses directly change rules, memory, architecture, task status, or acceptance status.
- Do not commit `*.local.json`, `*.local.yaml`, runtime registries, browser locks, raw Pro responses, profile ids, nonces, conversation ids, cookies, or tokens.
- Do not skip prompt validation, response validation, external feedback intake, or local decision gates.
- Do not mix Meta_workflow Pro session state with historical state from other projects.

## Decision Placement

- Put stable architecture direction in `docs/architecture/`.
- Put research/methodology interpretation in `docs/methodology/`.
- Put Pro review briefs and outcomes in `docs/pro_handoffs/` or Pro Bridge runtime/intake files as appropriate.
- Put executable Pro integration behavior in `integrations/pro_bridge/`.
- Keep `AGENTS.md` as an index and boundary document only.

## Local Work Loop

For substantial work: understand the goal, inspect repo state, gather evidence, plan or implement narrowly, validate, then record any durable decision in the right doc or subsystem.
