# Meta_workflow Knowledge Engine

This integration is a local Nexus-like knowledge compiler for Meta_workflow. It
turns repository documents into typed, cited artifacts and serves KnowQL-like
queries from SQLite.

The durable reproduction report is recorded in
`docs/architecture/nexus_like_reproduction_report.md`.

## Commands

```powershell
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py self-test
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py ingest
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py compile
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py query --file integrations/knowledge/examples/project_boundary.query.json
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py eval --suite meta_workflow_30 --compare baseline,compiled
```

Runtime files are written under `integrations/knowledge/runtime/` and are ignored
by Git.

## SEC 10-K Experiment

Copy the SEC config example and set a real User-Agent before downloading:

```powershell
Copy-Item integrations/knowledge/config/sec_10k_2022.example.json integrations/knowledge/config/sec_10k_2022.local.json
notepad integrations/knowledge/config/sec_10k_2022.local.json
```

Then run the large-corpus pipeline:

```powershell
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-download
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-normalize
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-compile
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-eval --suite sec_10k_150 --compare coding_sandbox,agentic_rag,compiled
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-judge-pack --suite sec_10k_150
```

Aliases are accepted for retrievers: `coding-sandbox`, `agentic-rag`, and
`compiled-artifacts`.

When SEC network access is unavailable, use already-downloaded Hugging Face SEC
10-K JSONL shards as a large-corpus mirror:

```powershell
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-import-hf --corpus sec_10k_hf_large
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-compile --corpus sec_10k_hf_large
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-eval --suite sec_10k_150 --corpus sec_10k_hf_large --compare coding_sandbox,agentic_rag,compiled --limit 150
C:\Users\dzw\anaconda3\python.exe integrations/knowledge/tools/knowledge.py sec-judge-pack --suite sec_10k_150 --corpus sec_10k_hf_large --compare coding_sandbox,agentic_rag,compiled --limit 150
```

`sec-eval` writes `comparison_summary.json` and `analysis_report.md` under the
corpus runtime `judge/` directory.

## ikunAim Project-Corpus Experiment

`ikunAim` is treated as a read-only external corpus. The adapter imports only
readable text/PDF-like files and writes all runtime artifacts under
`integrations/knowledge/runtime/ikunaim_full/`.

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

The typed artifacts cover project profile, workflow control, role gate, memory
system, run history, Pro feedback, and business context. `ikunaim_adaptive_40`
adds focused prompts for adaptive intake routing, role/domain selection, failure
recovery, Pro feedback absorption, and memory/boundary decisions. Automatic
metrics are completion, citation coverage, source-byte proxy, latency, and
steps; blind judge accuracy is exported/imported separately.

## Public KRAFTBench-like Reproduction

For a stricter public-method reproduction, keep the HF mirror as a sanity run
and use a separate corpus id for the official-aligned path:

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

The public KRAFT path writes `manifest_audit.json`, locked ground truth, agent
answer packs, blinded judge packs, judge summaries, and an official-delta report
under the corpus runtime directory. If SEC EDGAR is unreachable, the report is
marked as blocked and must not be described as a full public-method reproduction.
