# Pro Bridge defect escalation

Defects found during Pro Bridge operation must be classified before continuing.

Severity:

- `P0`: can cause wrong send, wrong target, leaked private state, or direct state mutation from Pro advice.
- `P1`: can cause bad review quality, incomplete capture, bad provenance, or unreliable counting.
- `P2`: cleanup, ergonomics, naming, documentation, or low-risk hardening.

Routing:

- P0 pauses all Pro sends.
- P1 pauses formal counting until resolved or explicitly deferred.
- P2 can be queued if the current run remains trustworthy.

Every defect should record `run_id`, `source_ref`, evidence path, owner, status, and next action.
