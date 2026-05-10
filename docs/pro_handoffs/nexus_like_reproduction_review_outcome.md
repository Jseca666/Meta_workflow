# Nexus-like Reproduction Pro Review Outcome

This file records the local intake outcome from the Pro review of commit
`590eefec824fbd292c5c31bdc918aa64f180dbb5`. It is a synthesized local decision
record, not the raw Pro response. The raw response should remain out of Git.

## Local Decision

Accepted as implementation guidance:

- Treat the work as a Nexus-like / KRAFTBench-style local behavior reproduction,
  not a Pinecone Nexus private implementation reproduction.
- Rename report metrics from `passed`/generic completion language to
  `auto_passed` and automatic completion where the score is deterministic.
- Keep blind judge accuracy separate from automatic completion and citation
  coverage.
- Add hidden user-written, negative/refusal, noisy-source, and stale/recovery
  tests before making stronger claims.
- Add minimal artifact staleness by recording source hashes at compile time and
  warning at query time when those hashes drift.
- Display `coding_sandbox` as `coding_sandbox_simulated` in reports because it
  is a file search/read simulation.

Deferred to later engineering:

- Full staging overlay with candidate/stable promotion.
- Context eval gates before artifact promotion.
- Incremental dependency graph beyond source-hash drift detection.
- Stronger RAG baseline with vector retrieval and learned reranking.
- Monitor/Evaluator integration using compiled context packets.

Rejected for current scope:

- Claiming exact Pinecone Nexus or private KRAFTBench reproduction.
- Treating automatic completion as human/LLM-judged accuracy.
- Committing raw Pro response text or runtime judge files.

## Implemented Follow-Up

- Added `ikunaim_hidden_30` with 30 hidden/adversarial typed-query cases.
- Added artifact version/status/source-hash metadata to SEC and ikunAim
  artifacts.
- Added `ikun-stale-check` and query-time `stale_artifact:<id>` warnings.
- Added baseline snippet citations for `coding_sandbox_simulated` and
  `agentic_rag`.
- Updated reports to separate automatic completion from future judge accuracy.

## Current Evidence Boundary

The current evidence supports the claim that compiled artifacts reduce
query-time source-byte proxy and improve typed, cited automatic completion on
the tested local suites. It does not yet support general RAG superiority claims
or judged factual-accuracy claims.
