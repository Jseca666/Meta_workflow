# External feedback absorption

External feedback includes Pro responses, human review, and tool summaries outside the local workflow gates.

## Intake rules

1. Preserve the raw response path and hash.
2. Validate response structure before recording findings.
3. Record confidence and remaining unknowns.
4. Split advice into findings with severity `P0`, `P1`, or `P2`.
5. Assign each finding an adoption decision: `accepted_for_followup`, `implemented`, `already_resolved`, `deferred`, or `rejected`.
6. Map accepted findings to local workflow work types.
7. Write only an intake and ledger entry first; memory writeback requires a later local gate.

## Trust policy

`trust_policy` is always `external_advice`. A Pro statement becomes project truth only after local verification.
