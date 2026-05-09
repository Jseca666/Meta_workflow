# Pro review package prompt

You are reviewing a Meta_workflow Pro Bridge package.

## Goal

- Review goal: {{review_goal}}
- Review scope: {{review_scope}}
- Out of scope: {{out_of_scope}}

## Source

- source_repo: {{source_repo}}
- source_ref: {{source_ref}}
- source_paths:
{{source_paths}}

If `source_ref` is empty, blocked, or marked draft-only, treat this as a draft package and do not assume GitHub contains the latest local state.

## Evidence Package

Use the local evidence package only as supporting evidence for logs, validation output, run summaries, environment notes, and reproduction notes. Do not treat a summary as a substitute for source.

## Required Response

Return a structured response that begins with `PRO_RESPONSE:` and ends with `PRO_RESPONSE_END`. Include confidence, findings by severity, fix order, and remaining unknowns.
