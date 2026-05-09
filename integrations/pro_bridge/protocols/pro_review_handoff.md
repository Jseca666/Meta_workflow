# Pro review handoff protocol

This protocol defines how Meta_workflow asks an external Pro expert for review while keeping local workflow state authoritative.

## Invariants

- Pro responses are external advice.
- Pro cannot directly mutate rules, memory, business direction, task status, or acceptance status.
- A formal review must have a fixed `source_ref` or an explicit block reason.
- Browser automation is limited to visible user-prepared windows.
- Guarded send is disabled unless the local config and the run both authorize it.

## Flow

1. Prepare source evidence: `source_repo`, `source_ref`, and `source_paths`.
2. Prepare local evidence: run notes, validation output, logs, screenshots, and manifests.
3. Build a prompt from `templates/pro_chat_prompt.md`.
4. Run `validate-prompt`.
5. Reconcile project sessions with `project-sessions`.
6. Lock the target browser window with `targets` and `lock`.
7. Use `fill`; then the user sends manually or the run performs guarded `send`.
8. Use `watch` or `capture` until observable completion gates pass.
9. Run `validate-response`.
10. Write `external_feedback_intake.yaml`.
11. Route findings through local decision gates before any memory or workflow writeback.

## Completion

A Pro response is formal only when it contains `PRO_RESPONSE:`, required confidence fields, structured findings, and `PRO_RESPONSE_END`. Short acknowledgements, partial thoughts, and draft replies can be saved as evidence but do not count as formal feedback.
