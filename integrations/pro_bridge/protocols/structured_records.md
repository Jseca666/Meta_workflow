# Structured records

Pro Bridge uses append-only structured records for auditability.

## Runtime ledgers

Runtime ledgers live under `integrations/pro_bridge/runtime/registries/` and are not committed.

Core ledgers:

- `pro_project_sessions.jsonl`
- `pro_test_sessions.jsonl`
- `pro_session_events.jsonl`
- `pro_review_receipts.jsonl`
- `external_feedback_ledger.jsonl`

## Common fields

Every formal Pro review record should include:

- `run_id`
- `source_ref`
- `pro_session_key`
- `prompt_path`
- `prompt_hash`
- `response_path`
- `response_hash`
- `validation_status`
- `confidence_percent`
- `adoption_decision`
- `created_at`

## Local-only fields

Never commit browser profile ids, send nonces, exact target ids, private conversation ids, raw captures, cookies, or tokens.
