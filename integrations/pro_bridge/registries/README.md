# Registry templates

Live Pro registries are local runtime state and are not committed.

Use `integrations/pro_bridge/templates/pro_project_session_record.jsonl` as the seed shape for `integrations/pro_bridge/runtime/registries/pro_project_sessions.jsonl`.

Runtime registry records should include:

- `run_id`
- `source_ref`
- `pro_session_key`
- `prompt_path`
- `prompt_hash`
- `response_path`
- `validation_status`
- `confidence_percent`
- `adoption_decision`
- `created_at`
