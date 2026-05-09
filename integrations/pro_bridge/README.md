# Pro Bridge

Pro Bridge is the reusable Meta_workflow integration for Pro-facing external expert review.

## Boundary

- Pro is an external expert, not the source of truth.
- Pro responses cannot directly change rules, long-term memory, business direction, or acceptance state.
- Every Pro response must be captured, validated, absorbed into a local intake record, and routed through local decision gates.
- Public files contain only protocols, templates, tools, and examples. Local profile ids, nonces, conversation ids, response captures, and session ledgers belong in `runtime/` or `*.local.*` files.

## CLI

```powershell
node integrations/pro_bridge/tools/pro_chat_monitor.mjs <command> --config integrations/pro_bridge/config/pro_chat_monitor.config.local.json
```

Supported commands are `self-test`, `probe`, `targets`, `lock`, `project-sessions`, `fill`, `snapshot`, `watch`, `capture`, `capture-latest`, `validate-prompt`, `validate-response`, and `send`.

## Review flow

`prepare evidence -> build prompt -> validate-prompt -> project-sessions -> targets/lock -> fill -> manual or guarded send -> watch/capture -> validate-response -> external_feedback_intake -> decision/memory writeback`

## Required prompt evidence

Each prompt sent to Pro must include `source_repo`, `source_ref`, `source_paths`, `review_goal`, `expected_output_schema`, and `local_evidence_manifest`. If a fixed source ref is not available, the prompt must state the block reason and Pro must treat the package as draft evidence.
