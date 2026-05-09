# Pro review request

source_repo: https://github.com/Jseca666/Meta_workflow
source_ref: BLOCKED_UNTIL_FIRST_COMMIT
source_paths:
- integrations/pro_bridge/README.md
- integrations/pro_bridge/tools/pro_chat_monitor.mjs
- integrations/pro_bridge/protocols/pro_review_handoff.md

review_goal: Review whether the Pro Bridge workflow safely connects Meta_workflow to an external Pro expert.
local_evidence_manifest: integrations/pro_bridge/templates/pro_material_manifest.md

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

Please cite the files you actually inspected. If the fixed `source_ref` is blocked, treat this as a draft package and list the missing evidence.
