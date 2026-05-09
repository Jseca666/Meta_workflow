# Pro chat prompt

You are reviewing Meta_workflow as an external workflow-engine expert.

source_repo: {{source_repo}}
source_ref: {{source_ref}}
source_ref_status: {{source_ref_status}}
source_paths:
{{source_paths}}

review_goal: {{review_goal}}
local_evidence_manifest: {{local_evidence_manifest}}

Please focus on:

- Whether this Pro Bridge safely uses an external expert without letting the expert directly mutate project truth.
- Whether prompt validation, browser-window locking, guarded send, capture, and response validation are sufficient.
- Whether memory writeback is separated from external advice.
- Whether any missing evidence blocks a confident review.

expected_output_schema:
```text
PRO_RESPONSE:
confidence_percent: <0-100>
is_100_percent_confident: <yes|no>
overall_judgment:
all_findings:
  - id:
    severity: <P0|P1|P2>
    title:
    evidence:
    recommendation:
fix_order:
remaining_unknowns:
PRO_RESPONSE_END
```

Rules:

- Cite the files and paths you actually inspected.
- If `source_ref` is blocked or draft-only, do not assume the public repository is synchronized.
- Do not ask to directly change project memory, rules, or acceptance status.
- If evidence is insufficient, list the missing evidence and its impact.
