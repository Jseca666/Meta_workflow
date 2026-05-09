# AGENTS.md

This is the root operating contract for Codex in Meta_workflow. Read it before `README.md` when working in this repository.

## Project Goal

Meta_workflow is a meta workflow engine project. Its goal is to guide the construction of business workflows for arbitrary projects, then evolve into a complete workflow engine with planning, execution, validation, memory, recall, and external expert review.

The guiding methodology is MAP-style modular planning from the paper `references/papers/s41467-025-63804-5.pdf`: decompose goals, propose actions, monitor constraints, predict consequences, evaluate states, orchestrate progress, and write back verified memory.

## Codex Work Loop

Use this loop for substantial work:

1. Understand the user goal and current repository state.
2. Gather evidence from source files, runtime records, papers, and prior decisions.
3. Produce or update a fixed GitHub `source_ref` for any external review.
4. If Pro review is needed, route it through Pro Bridge.
5. Treat Pro output as external advice.
6. Validate and absorb findings locally before changing rules, memory, architecture, or acceptance status.

## Pro Bridge Is Mandatory

All Pro interaction in this repository must go through `integrations/pro_bridge`.

Read these files before preparing a Pro handoff:

- `integrations/pro_bridge/README.md`
- `integrations/pro_bridge/protocols/pro_review_handoff.md`
- `integrations/pro_bridge/protocols/external_feedback_absorption.md`
- `integrations/pro_bridge/protocols/source_ref_provenance.md`

The normal Pro path is:

`prepare evidence -> build prompt -> validate-prompt -> project-sessions -> targets/lock -> fill or manual paste -> capture -> validate-response -> external_feedback_intake -> local decision/memory writeback`

## GitHub Source Ref Rule

Pro should read project materials through GitHub whenever possible. Prompts to Pro must include:

- `source_repo`: `https://github.com/Jseca666/Meta_workflow`
- `source_ref`: a fixed commit URL such as `https://github.com/Jseca666/Meta_workflow/tree/<commit-sha>`
- `source_paths`: exact files or folders to inspect
- `review_goal`
- `expected_output_schema`
- `local_evidence_manifest`

Do not ask Pro to infer from "latest local files" or unstaged work. If the fixed ref is unavailable, state the block reason and mark the review as draft-only.

## Current First Pro Review Materials

The first Pro review should ask Pro to:

- read `references/papers/s41467-025-63804-5.pdf`
- understand MAP's modules and planning methodology
- understand that Meta_workflow aims to become a workflow engine for building project-specific business workflows
- propose a first complete project architecture for Meta_workflow

## Non-Negotiable Boundaries

- Pro is an external expert, not the source of truth.
- Pro responses cannot directly change workflow rules, long-term memory, business direction, task status, or acceptance status.
- Do not commit `*.local.json`, `*.local.yaml`, runtime registries, browser locks, raw Pro responses, profile ids, nonces, conversation ids, cookies, or tokens.
- Do not skip prompt validation, response validation, external feedback intake, or local decision gates.
- Do not mix Meta_workflow Pro session state with `ikunAim` historical Pro sessions.
