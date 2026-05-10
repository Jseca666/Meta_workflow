# Nexus-like Knowledge Compiler Reproduction Report

This report records the local behavior-reproduction work after implementing the
Meta_workflow knowledge compiler. It is a Nexus-like / KRAFTBench-style
public-behavior prototype, not Pinecone Nexus internals and not Pinecone private
benchmark data.

For Pro review, use `docs/pro_handoffs/nexus_like_reproduction_review.md`.

## Goal

The goal was to test whether moving knowledge work from query time to build time
can make agent answers more reliable on complex corpora.

The reproduced behavior is:

- build-time compilation from raw sources into typed artifacts;
- query-time declarative requests with `ask`, `contexts`, `where`, `shape`,
  `ground`, `confidence`, and `budget`;
- typed answers with field-level citations and confidence;
- comparison against simulated raw file-search and chunk/RAG baselines;
- budget reporting with latency, steps, and source-byte proxy.

The implementation is local and deterministic at runtime. It uses Python
standard library modules and SQLite/FTS5.

## Implementation

Entry point:

```powershell
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py <command>
```

Main code:

- `integrations/knowledge/tools/knowledge.py`
- `integrations/knowledge/README.md`
- `docs/architecture/knowledge_engine.md`

Runtime outputs:

- `integrations/knowledge/runtime/`

Runtime data is intentionally ignored by Git.

## Knowledge Model

The local model is:

```text
Source -> Artifact -> Context -> Knowledge
```

- `Source`: raw readable file with path, hash, byte count, content, and line
  anchors.
- `Artifact`: typed, task-oriented knowledge object compiled from one or more
  sources.
- `Context`: query-addressable group of artifacts.
- `Knowledge`: all contexts available to the query layer.

For `ikunAim`, the compiler emits seven artifacts:

| artifact | purpose |
| --- | --- |
| `project_profile` | project goal, workflow driver, business direction, legacy boundary |
| `workflow_control` | mandatory loop, stop rule, validation gates, current pointers |
| `role_gate` | I0-I9 classification, role/domain routing, gate rule |
| `memory_system` | memory paths, writeback boundary, memory queue sources |
| `run_history` | latest runs, task index, defect/event ledger, handoff evidence |
| `pro_feedback` | Pro intake, absorption status, visible-send guard, audit closure |
| `business_context` | AI/scrcpy/Android direction, old project boundary, noisy sources |

## Query Contract

Queries are JSON objects. Example:

```json
{
  "ask": "What is the current ikunAim workflow state?",
  "contexts": ["ikunaim_workflow", "ikunaim_runs"],
  "where": {"principal_tags": ["public"]},
  "ground": true,
  "shape": {
    "type": "object",
    "properties": {
      "current_run_id": {"type": "string"},
      "current_task_id": {"type": "string"},
      "validation_gates": {"type": "array"}
    }
  },
  "confidence": {"min": 0.6},
  "budget": {"depth": "standard", "latency_ms": 1000}
}
```

The response is strict JSON:

- `answer`
- `fields`
- `citations`
- `confidence`
- `budget_used`
- `filtered_by_acl`
- `warnings`

## Corpus Results

### SEC HF 10-K Mirror

This is a large-corpus sanity reproduction, not the official 2022 EDGAR corpus
and not Pinecone private KRAFTBench.

Corpus:

- 870 filings
- 235 latest-company artifacts
- 87,237 chunks
- 259.897 MiB normalized text
- suite: `sec_10k_150`

| retriever | auto_passed | automatic completion | median latency ms | source-byte proxy | avg steps | citation coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `coding_sandbox_simulated` | 78/150 | 0.520 | 6.750 | 86,308,997 | 17.900 | 0.000 |
| `agentic_rag` | 23/150 | 0.153 | 15.429 | 12,995,235 | 26.880 | 0.000 |
| `compiled` | 150/150 | 1.000 | 3.746 | 325,304 | 1.000 | 1.000 |

Compiled source-byte reduction versus agentic RAG: `39.948x`.

### ikunAim Full Project Corpus

This corpus is an external project directory imported read-only from
`C:\Users\dzw\Desktop\ikunAim`.

Corpus:

- 1,224 readable sources
- 1,917 chunks
- 7 typed artifacts
- 3.504 MiB readable text
- 264 noisy sources from `temp/`, `reference_materials/`, and Pro captures
- suite: `ikunaim_90`

| retriever | auto_passed | automatic completion | median latency ms | source-byte proxy | avg steps | citation coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `coding_sandbox_simulated` | 59/90 | 0.656 | 66.069 | 17,722,034 | 23.122 | 1.000 |
| `agentic_rag` | 49/90 | 0.544 | 4.289 | 4,330,960 | 22.556 | 1.000 |
| `compiled` | 90/90 | 1.000 | 2.501 | 134,622 | 1.000 | 1.000 |

Compiled source-byte reduction versus agentic RAG: `32.171x`.

Covered prompt classes:

- 30 cross-document workflow questions;
- 25 failure/audit-chain questions;
- 20 business-boundary questions;
- 15 integrated decision questions.

### ikunAim Adaptive Workflow Suite

This suite specifically tests original workflow-adaptation prompts: vague user
intake, role/domain selection, failure recovery, Pro feedback absorption, and
memory/boundary decisions.

Suite: `ikunaim_adaptive_40`

| category | cases |
| --- | ---: |
| adaptive intake routing | 10 |
| adaptive role/domain selection | 10 |
| adaptive failure recovery | 8 |
| adaptive Pro absorption | 6 |
| adaptive memory and boundary | 6 |

| retriever | auto_passed | automatic completion | median latency ms | source-byte proxy | avg steps | citation coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `coding_sandbox_simulated` | 24/40 | 0.600 | 80.085 | 10,467,786 | 22.600 | 1.000 |
| `agentic_rag` | 26/40 | 0.650 | 6.622 | 2,072,014 | 24.150 | 1.000 |
| `compiled` | 40/40 | 1.000 | 2.835 | 91,158 | 1.000 | 1.000 |

Compiled source-byte reduction versus agentic RAG: `22.730x`.

### ikunAim Hidden/Adversarial Suite

This suite was added after Pro feedback to reduce artifact-schema overfitting.
Questions are hand-written natural-language prompts rather than direct variants
of artifact field names. The suite still uses a KnowQL `shape`, so these are
hidden user-written typed-query tests, not unconstrained chat accuracy tests.

Suite: `ikunaim_hidden_30`

| category | cases |
| --- | ---: |
| hidden cross-boundary | 10 |
| negative/refusal | 10 |
| noisy source | 5 |
| stale/recovery | 5 |

| retriever | auto_passed | automatic completion | median latency ms | source-byte proxy | avg steps | citation coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `coding_sandbox_simulated` | 14/30 | 0.467 | 84.430 | 8,557,384 | 23.167 | 1.000 |
| `agentic_rag` | 16/30 | 0.533 | 5.691 | 1,573,290 | 23.967 | 1.000 |
| `compiled` | 30/30 | 1.000 | 2.634 | 66,082 | 1.000 | 1.000 |

Compiled source-byte reduction versus agentic RAG: `23.808x`.

Failure categories for the two baselines concentrate on wrong run/task joins,
noisy temp capture, and ambiguous business boundaries. The current automatic
metric still does not prove judged factual accuracy; a blind judge pack was
exported and awaits imported `judge_results.jsonl`.

## Why The Compiled Path Wins

The strongest result appears on workflow-adaptation prompts because these prompts
are not simple semantic lookup. They require joining several policy facts:

- task classification;
- role/domain gate;
- current run and task pointers;
- stop and validation gates;
- stale-state recovery rules;
- Pro feedback intake and absorption boundaries;
- memory writeback eligibility;
- noisy source and legacy-project boundaries.

Simulated raw file search and the current local RAG baseline retrieve snippets
at query time. They often find relevant nearby text but miss one or more required
policy fields, or retrieve noisy captures from `temp/` and historical runs.

The compiled path converts those scattered facts into typed artifacts before the
query. Query time is then mostly:

```text
route contexts -> look up typed fields -> attach citations -> return JSON
```

This is the practical meaning of moving runtime reasoning pressure to build
time.

## Cost Model

The cost is not free, but it is front-loaded.

Build-time costs:

- source scanning and normalization;
- source hashing;
- artifact schema design;
- deterministic extraction and citation anchoring;
- stale-artifact checks when sources change.

Query-time savings:

- fewer source bytes read;
- fewer retrieval steps;
- stable typed outputs;
- field-level citations without re-reading full sources;
- lower risk of noisy context dominating the answer.

For the `ikunAim` corpus, the build/import/compile path is second-scale on the
local machine. The query median for compiled artifacts is approximately
`2-4 ms` across the rerun suites.

The real engineering cost is schema quality. A poor artifact schema can freeze
the wrong abstraction. A good artifact schema turns repeated multi-hop reasoning
into a small lookup.

## Rigor And Boundaries

These results are automatic metrics, not final human or LLM-judge accuracy.

Evidence tiers:

| tier | purpose | current status |
| --- | --- | --- |
| artifact-aligned | validate artifact schema coverage on intended tasks | covered by `meta_workflow_30`, `sec_10k_150`, `ikunaim_90`, `ikunaim_adaptive_40` |
| hidden user-written | test natural-language prompts not generated from artifact field names | covered by `ikunaim_hidden_30` |
| source-grounded adversarial | require answers from source facts outside current artifact schema | planned |
| drift/stale | verify source hash drift and stale warnings | minimal `ikun-stale-check` implemented; mutation regression covered in self-test |

Current rigor level:

- deterministic corpus import;
- source hashes and artifact source-hash manifests;
- artifact stale warnings for source hash drift;
- field-level citations;
- baseline snippet citations for simulated file search and RAG;
- held runtime outputs;
- three-path comparison;
- failure categories;
- blinded judge pack export.

Pending for stronger claims:

- import independent judge results from `judge_results.jsonl`;
- add source-grounded adversarial tasks outside the current artifact schema;
- strengthen citation-support judging beyond citation presence;
- implement staging overlay and context eval before promotion;
- add incremental compilation instead of full recompile.

## Reproduction Commands

Self-test:

```powershell
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py self-test
```

Run `ikunAim` full corpus:

```powershell
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ikun-ingest --root C:\Users\dzw\Desktop\ikunAim --corpus ikunaim_full --scope full-readable
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ikun-compile --corpus ikunaim_full
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ikun-eval --suite ikunaim_90 --corpus ikunaim_full --compare coding_sandbox,agentic_rag,compiled --limit 90
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ikun-eval --suite ikunaim_adaptive_40 --corpus ikunaim_full --compare coding_sandbox,agentic_rag,compiled --limit 40
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ikun-eval --suite ikunaim_hidden_30 --corpus ikunaim_full --compare coding_sandbox,agentic_rag,compiled --limit 30
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ikun-stale-check --corpus ikunaim_full
```

Generate judge packs:

```powershell
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ikun-agent-pack --suite ikunaim_90 --corpus ikunaim_full --retriever coding_sandbox,agentic_rag,compiled --composer codex
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ikun-judge-pack --suite ikunaim_90 --corpus ikunaim_full --blind --judge codex
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ikun-agent-pack --suite ikunaim_hidden_30 --corpus ikunaim_full --retriever coding_sandbox,agentic_rag,compiled --composer codex --limit 30
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ikun-judge-pack --suite ikunaim_hidden_30 --corpus ikunaim_full --blind --judge codex --limit 30
```

SEC HF mirror:

```powershell
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-import-hf --corpus sec_10k_hf_large
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-compile --corpus sec_10k_hf_large
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-eval --suite sec_10k_150 --corpus sec_10k_hf_large --compare coding_sandbox,agentic_rag,compiled --limit 150
```

## Claim Supported

Supported:

- Build-time compiled artifacts reduce query-time source-byte proxy on repeated,
  structured knowledge tasks in these local suites.
- Typed artifacts produce complete, cited JSON outputs more reliably than raw
  file-search simulation or the current local chunk-RAG baseline on the tested
  corpora.
- The effect is especially strong for workflow-adaptation prompts where the
  answer depends on policy joins rather than one nearby snippet.

Not yet supported:

- Exact Pinecone Nexus internals.
- Exact Pinecone KRAFTBench benchmark reproduction.
- Human/LLM-judged final accuracy.
- General superiority on all open-ended generation tasks.
