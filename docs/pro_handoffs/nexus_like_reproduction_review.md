# Nexus-like Knowledge Compiler Reproduction Review

This is a Pro handoff brief for reviewing the local Nexus/KRAFTBench-like
knowledge compiler reproduction.

## Boundary

This package asks Pro to review a local public-behavior reproduction. It does
not claim Pinecone Nexus internals, Pinecone private KRAFTBench access, or exact
official 2022 SEC corpus reproduction.

Pro output is external advice only. It cannot directly change architecture,
rules, memory, acceptance status, or benchmark claims. Any findings must go
through local feedback intake and decision gates.

## Source Repo

- Repository: `https://github.com/Jseca666/Meta_workflow`
- Source ref reviewed by Pro: `590eefec824fbd292c5c31bdc918aa64f180dbb5`.
- Follow-up outcome: `docs/pro_handoffs/nexus_like_reproduction_review_outcome.md`.

## Source Paths

Primary review documents:

- `docs/architecture/nexus_like_reproduction_report.md`
- `docs/architecture/knowledge_engine.md`
- `integrations/knowledge/README.md`

Implementation and examples:

- `integrations/knowledge/tools/knowledge.py`
- `integrations/knowledge/examples/project_boundary.query.json`
- `integrations/knowledge/examples/ikunaim_workflow.query.json`

Runtime evidence is ignored by Git and should be treated as local experiment
output, not durable source truth:

- `integrations/knowledge/runtime/sec_10k_hf_large/judge/comparison_summary.json`
- `integrations/knowledge/runtime/ikunaim_full/comparison_summary.json`
- `integrations/knowledge/runtime/ikunaim_full/comparison_summary.ikunaim_adaptive_40.json`
- `integrations/knowledge/runtime/ikunaim_full/analysis_report.md`
- `integrations/knowledge/runtime/ikunaim_full/analysis_report.ikunaim_adaptive_40.md`
- `integrations/knowledge/runtime/ikunaim_full/analysis_report.ikunaim_hidden_30.md`

## Local Evidence Manifest

Implemented behavior:

- Python standard-library CLI with SQLite/FTS5.
- Local knowledge model: `Source -> Artifact -> Context -> Knowledge`.
- KnowQL-like query contract with `ask`, `contexts`, `where`, `shape`,
  `ground`, `confidence`, and `budget`.
- Strict JSON response with `answer`, `fields`, `citations`, `confidence`,
  `budget_used`, `filtered_by_acl`, and `warnings`.
- Three retrieval paths:
  - `coding_sandbox`: simulated file search/read loop, displayed in reports as
    `coding_sandbox_simulated`.
  - `agentic_rag`: chunk FTS with expansion/fusion-style retrieval.
  - `compiled`: artifact routing and typed field lookup.
- Blinded judge pack export exists, but independent judge results are not yet
  imported.

SEC HF mirror result:

- Corpus: 870 filings, 235 latest-company artifacts, 87,237 chunks,
  259.897 MiB normalized text.
- Suite: `sec_10k_150`.
- `compiled`: 150/150 automatic completion, 3.746 ms median latency, 325,304 source-byte
  proxy, 1.000 citation coverage.
- `agentic_rag`: 23/150 automatic completion, 15.429 ms median latency, 12,995,235
  source-byte proxy.
- `coding_sandbox_simulated`: 78/150 automatic completion, 6.750 ms median latency, 86,308,997
  source-byte proxy.

ikunAim project corpus result:

- Corpus: 1,224 readable sources, 1,917 chunks, 7 typed artifacts,
  3.504 MiB readable text, 264 noisy sources.
- Suite: `ikunaim_90`.
- `compiled`: 90/90 automatic completion, 2.501 ms median latency, 134,622 source-byte
  proxy, 1.000 citation coverage.
- `agentic_rag`: 49/90 automatic completion, 4.289 ms median latency, 4,330,960
  source-byte proxy, 1.000 citation coverage.
- `coding_sandbox_simulated`: 59/90 automatic completion, 66.069 ms median latency, 17,722,034
  source-byte proxy, 1.000 citation coverage.

ikunAim adaptive workflow result:

- Suite: `ikunaim_adaptive_40`.
- Prompt classes: adaptive intake routing, role/domain selection, failure
  recovery, Pro feedback absorption, memory/boundary decisions.
- `compiled`: 40/40 automatic completion, 2.835 ms median latency, 91,158 source-byte
  proxy, 1.000 citation coverage.
- `agentic_rag`: 26/40 automatic completion, 6.622 ms median latency, 2,072,014
  source-byte proxy, 1.000 citation coverage.
- `coding_sandbox_simulated`: 24/40 automatic completion, 80.085 ms median latency, 10,467,786
  source-byte proxy, 1.000 citation coverage.

ikunAim hidden/adversarial follow-up result:

- Suite: `ikunaim_hidden_30`.
- Prompt classes: hidden cross-boundary, negative/refusal, noisy source,
  stale/recovery.
- `compiled`: 30/30 automatic completion, 2.634 ms median latency, 66,082
  source-byte proxy, 1.000 citation coverage.
- `agentic_rag`: 16/30 automatic completion, 5.691 ms median latency,
  1,573,290 source-byte proxy, 1.000 citation coverage.
- `coding_sandbox_simulated`: 14/30 automatic completion, 84.430 ms median
  latency, 8,557,384 source-byte proxy, 1.000 citation coverage.

Validation already run:

- `knowledge.py self-test`: 12/12 passed after follow-up hardening.
- `git diff --check`: passed.

## Review Goal

Please review whether the reproduction is technically meaningful and whether
the claims in `docs/architecture/nexus_like_reproduction_report.md` are
appropriately scoped.

Focus on:

- whether the artifact schema is a fair implementation of the public
  Nexus/KnowQL behavior;
- whether the benchmarks overstate the compiled path because questions are
  generated from the same artifacts;
- whether the `coding_sandbox` and `agentic_rag` baselines are fair enough for a
  local experiment;
- whether the source-byte, latency, step, completion, and citation metrics are
  meaningful;
- what additional hidden/adversarial tests are needed before stronger claims;
- how to design an independent judge workflow without leaking retriever identity
  or artifact-derived expected answers;
- what engineering is needed for incremental compilation and stale-artifact
  handling;
- whether the result is useful for the Meta_workflow/ikunAim adaptive workflow
  engine direction.

## Specific Questions

1. Which claims in the report are supported by the current evidence, and which
   claims should be softened?
2. Is `Source -> Artifact -> Context -> Knowledge` the right abstraction for
   this project, or is another layer missing?
3. Are the seven `ikunAim` artifacts too hand-curated, or is that an acceptable
   build-time schema for workflow governance?
4. How should hidden tests be designed so the suite does not simply reward the
   compiled artifact schema?
5. What would make the SEC HF mirror experiment more rigorous without requiring
   private KRAFTBench data?
6. Should the adaptive workflow suite include negative/refusal prompts, and what
   examples should be added?
7. What is the minimum incremental compilation design needed before using this
   in a live workflow engine?
8. What failure categories should be tracked beyond the current set?

## Expected Output

The response must start with `PRO_RESPONSE:` and end with `PRO_RESPONSE_END`.

Required sections:

- reproduction_understanding
- claim_audit
- benchmark_design_review
- artifact_schema_review
- baseline_fairness_review
- adaptive_workflow_relevance
- missing_rigor_checks
- recommended_hidden_tests
- incremental_compilation_design
- risks_and_failure_modes
- next_tasks

## Handling Result

After capture:

1. Validate the response envelope and required sections.
2. Record external feedback intake.
3. Classify findings by severity and topic.
4. Decide locally which findings become tasks.
5. Do not write findings directly into memory or acceptance status.
