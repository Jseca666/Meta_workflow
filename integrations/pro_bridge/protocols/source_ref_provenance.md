# Source ref provenance

Formal Pro review must be anchored to immutable source evidence.

Required prompt fields:

- `source_repo`
- `source_ref`
- `source_paths`
- `review_goal`
- `expected_output_schema`
- `local_evidence_manifest`

If `source_ref` is not available, the prompt must state the block reason. Pro may still review a draft package, but the result cannot be counted as final source-grounded review.

Preferred source ref format:

```text
https://github.com/Jseca666/Meta_workflow/tree/<commit-sha>
```
