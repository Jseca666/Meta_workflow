# Nexus-like Knowledge Engine

This document records the local Meta_workflow interpretation of Pinecone Nexus and
KnowQL. It is a reverse-engineering plan and implementation guide, not a claim
about Pinecone's private internals.

For the post-implementation reproduction report and measured results, see
`docs/architecture/nexus_like_reproduction_report.md`.

## Publicly Described Behavior

Pinecone describes Nexus as a knowledge engine for agents. The public materials
center on these behaviors:

- Compile data into trusted, task-specific artifacts before query time.
- Serve typed answers instead of ranked chunks.
- Attach field-level citations and confidence tiers.
- Enforce access-control and deterministic predicates at the query surface.
- Let agents declare intent, filters, grounding, shape, confidence, and budget
  through KnowQL-like primitives.
- Evaluate the result against end-to-end task accuracy, latency, token use, and
  completion rate rather than retrieval recall alone.

## Local Product Goal

Meta_workflow needs a small, local knowledge layer that gives Codex and future
workflow agents a stable way to ask for project knowledge without rereading the
whole repository each time. The first local version uses the repository itself as
the domain corpus and compiles architecture, methodology, governance, and Pro
Bridge facts into typed artifacts.

The local knowledge model is:

```text
Source -> Artifact -> Context -> Knowledge
```

- `Source`: a tracked repository document with content hash and line anchors.
- `Artifact`: a typed, versioned fact object built for a task or workflow.
- `Context`: a governed set of artifacts for a role or workflow.
- `Knowledge`: the complete set of contexts available to a query.

## Local Implementation

The first implementation lives under `integrations/knowledge/` and is intentionally
dependency-light. It uses Python standard library modules and SQLite:

```powershell
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py self-test
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ingest
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py compile
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py query --file integrations/knowledge/examples/project_boundary.query.json
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py eval --suite meta_workflow_30 --compare baseline,compiled
```

Runtime databases and ledgers stay under `integrations/knowledge/runtime/` and are
ignored by Git.

## KnowQL-like Query Contract

A query is JSON with these top-level fields:

- `ask`: natural-language task intent.
- `contexts`: context ids to search.
- `where`: deterministic predicates and caller tags.
- `ground`: whether field-level citations are required.
- `shape`: JSON-schema-like output shape.
- `confidence`: minimum confidence requirements.
- `budget`: depth, latency, max artifact, and source-byte controls.

The engine returns strict JSON with:

- `answer`
- `fields`
- `citations`
- `confidence`
- `budget_used`
- `filtered_by_acl`
- `warnings`

## Evaluation

The local benchmark is `meta_workflow_30`: 30 questions over repository facts.
It compares:

- `baseline`: raw-source FTS/snippet retrieval.
- `compiled`: artifact/context retrieval.

Passing criteria for the compiled path:

- Completion at or above 90%.
- Grounded fields have citations.
- Median query latency below 1 second on the local corpus.
- Source-byte/token proxy at least 5x smaller than baseline.

## SEC 10-K Large-Corpus Replication

The large-corpus replication path targets a Pinecone Nexus/KRAFTBench-style
experiment without claiming access to Pinecone's private benchmark or internal
implementation.

Pipeline:

```powershell
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-download
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-normalize
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-compile
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-eval --suite sec_10k_150 --compare coding_sandbox,agentic_rag,compiled
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-judge-pack --suite sec_10k_150
```

The SEC path adds:

- `sec-download`: downloads company ticker metadata, submissions, 2022 10-K
  primary documents, and companyfacts JSON.
- `sec-normalize`: converts SEC HTML/SGML into normalized text and section
  anchors.
- `sec-compile`: builds one `company_fact_sheet` artifact per filing and chunks
  normalized text for RAG comparison.
- `sec-eval`: compares `coding_sandbox`, `agentic_rag`, and `compiled`.
- `sec-judge-pack`: exports JSONL for Codex/LLM human-in-the-loop judging.

Runtime corpus files live under `integrations/knowledge/runtime/sec_10k_2022/`
and remain ignored by Git. Downloading requires
`integrations/knowledge/config/sec_10k_2022.local.json` with a real SEC
User-Agent string.

### Hugging Face SEC 10-K Mirror

If the local network cannot reach SEC EDGAR reliably, the experiment can use a
downloaded Hugging Face SEC 10-K mirror as `sec_10k_hf_large`:

```powershell
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-import-hf --corpus sec_10k_hf_large
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-compile --corpus sec_10k_hf_large
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-eval --suite sec_10k_150 --corpus sec_10k_hf_large --compare coding_sandbox,agentic_rag,compiled --limit 150
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-judge-pack --suite sec_10k_150 --corpus sec_10k_hf_large --compare coding_sandbox,agentic_rag,compiled --limit 150
```

This mirror path is a public-data, large-corpus replication only. It records the
actual filing years in the manifest and report, and it must not be described as
Pinecone's private KRAFTBench corpus or as the official 2022 EDGAR set.

## ikunAim Project-Corpus Path

The `ikunaim_full` path tests the same knowledge-compiler idea on a dense
external project corpus instead of financial filings. The source root is
`C:\Users\dzw\Desktop\ikunAim`; the adapter treats it as read-only and writes
all runtime state back into Meta_workflow.

```powershell
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ikun-ingest --root C:\Users\dzw\Desktop\ikunAim --corpus ikunaim_full --scope full-readable
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ikun-compile --corpus ikunaim_full
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ikun-query --corpus ikunaim_full --file integrations/knowledge/examples/ikunaim_workflow.query.json
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ikun-eval --suite ikunaim_90 --corpus ikunaim_full --compare coding_sandbox,agentic_rag,compiled
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ikun-eval --suite ikunaim_adaptive_40 --corpus ikunaim_full --compare coding_sandbox,agentic_rag,compiled --limit 40
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ikun-agent-pack --suite ikunaim_90 --corpus ikunaim_full --retriever coding_sandbox,agentic_rag,compiled --composer codex
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ikun-judge-pack --suite ikunaim_90 --corpus ikunaim_full --blind --judge codex
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ikun-analysis --suite ikunaim_90 --corpus ikunaim_full
```

The compiler emits seven typed artifacts:

- `project_profile`: project goal, business direction, old-project boundary,
  workflow driver, and success boundary.
- `workflow_control`: mandatory loop, stop rule, red lines, current run pointer,
  current task pointer, trusted sources, and validation gates.
- `role_gate`: I0-I9 classification, role/domain routing, and gate rule.
- `memory_system`: memory paths, writeback boundary, direction memory,
  engineering strategy, and failure review sources.
- `run_history`: latest runs, task index sources, handoff/validation sources,
  defect/event ledger sources, and stale-current-run risk.
- `pro_feedback`: Pro feedback sources, external-feedback intake,
  visible-send/confirmation guard, absorption status, and audit closure.
- `business_context`: AI/scrcpy/Android control direction, read-only legacy
  boundary, no-migration policy, business samples, and noisy reference sources.

The `ikunaim_90` benchmark has 30 workflow questions, 25 audit/failure-chain
questions, 20 business-boundary questions, and 15 integrated decision questions.
Its automatic score is not a substitute for blind judge accuracy; it measures
whether the retrieval path returns typed fields, citations, lower source-byte
proxy, lower step count, and fast local latency.

The narrower `ikunaim_adaptive_40` suite focuses on original workflow adaptation
prompts: vague user intake routing, role/domain selection, failure recovery,
Pro-feedback absorption, and memory/boundary decisions.

### Public KRAFTBench-like Path

The stricter reproduction path uses a separate corpus id,
`sec_10k_2022_kraft_public`, and only becomes a public-method reproduction after
three gates pass: official SEC corpus audit, locked independent ground truth, and
blinded Codex judge import.

```powershell
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-manifest-build --corpus sec_10k_2022_kraft_public --as-of 2022-12-31 --target-filings 493
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-download --corpus sec_10k_2022_kraft_public --resume --audit
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-normalize --corpus sec_10k_2022_kraft_public --target-mb 245
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-compile --corpus sec_10k_2022_kraft_public
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-groundtruth-build --suite kraft_public_150 --corpus sec_10k_2022_kraft_public --lock
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-agent-pack --suite kraft_public_150 --corpus sec_10k_2022_kraft_public --retriever coding_agent,agentic_rag,compiled --composer codex --budget-seconds 120 --token-budget 1000000
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-agent-import --suite kraft_public_150 --corpus sec_10k_2022_kraft_public --input integrations/knowledge/runtime/sec_10k_2022_kraft_public/agent_answers.jsonl
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-judge-pack --suite kraft_public_150 --corpus sec_10k_2022_kraft_public --blind --judge codex
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-judge-import --suite kraft_public_150 --corpus sec_10k_2022_kraft_public --input integrations/knowledge/runtime/sec_10k_2022_kraft_public/judge_results.jsonl
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-analysis --suite kraft_public_150 --corpus sec_10k_2022_kraft_public --compare-official-pinecone
```

This path intentionally separates:

- `manifest_audit.json`: corpus coverage, SEC download status, 2022 match rate,
  missing tickers, duplicate share classes, and hash drift.
- `groundtruth_150.locked.jsonl`: independent companyfacts/text-derived answers,
  not derived from compiled artifacts.
- `agent_pack.jsonl` and `agent_answers.jsonl`: retrieval evidence and Codex
  composer output.
- `judge_pack.blind.jsonl`, `judge_answer_key.json`, and `judge_results.jsonl`:
  blinded Codex judge workflow.
- `kraft_comparison_report.md` and `official_delta_table.json`: completion,
  accuracy, latency, token_proxy, and steps compared with Pinecone's public
  table.

## Boundaries

- This is not Pinecone Nexus and does not use Pinecone infrastructure.
- The local compiler is deterministic in runtime. Codex may be used as a
  development-time iteration loop by editing `curate()` and `query()` behavior.
- Pro responses remain external advice. They cannot directly mutate rules,
  memory, business direction, task status, or acceptance status.
