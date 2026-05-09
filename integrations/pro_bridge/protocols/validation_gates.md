# Validation gates

## Before fill or send

- `validate-prompt` passes.
- `source_ref` is fixed or blocked with a clear reason.
- browser window lock is exact and unexpired.
- project session reconciliation passes for formal runs.

## Before capture acceptance

- completion is derived from observable browser state.
- captured response is from the locked project conversation.
- response path and hash are recorded.

## Before memory or workflow writeback

- `validate-response` returns `schema_valid`.
- external feedback intake is written.
- local decision gate records an adoption decision.
