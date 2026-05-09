# Meta_workflow

Meta_workflow is a meta workflow engine workspace. Its goal is to guide arbitrary projects through business workflow design, execution, validation, memory, recall, and evolution.

Codex and human contributors should read `AGENTS.md` first. It is intentionally lightweight and routes work to the right subsystem documents.

## Repository Map

- `AGENTS.md`: root entry contract and routing rules.
- `docs/architecture/vision.md`: project direction, target users, engine shape, and roadmap.
- `docs/methodology/map_methodology.md`: MAP paper methodology adapted for Meta_workflow.
- `docs/pro_handoffs/first_architecture_review.md`: first Pro architecture review brief.
- `integrations/pro_bridge/`: guarded external Pro expert integration.
- `references/papers/s41467-025-63804-5.pdf`: source paper for MAP-style modular planning.

## Operating Boundaries

- Pro feedback is external advice until locally validated and absorbed.
- Runtime captures, local configs, browser locks, local registries, and Pro responses stay ignored under `integrations/pro_bridge/runtime/` or `*.local.*`.
- Public review material should be shared through fixed GitHub commit refs.
