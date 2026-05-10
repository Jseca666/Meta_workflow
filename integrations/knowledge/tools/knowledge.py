#!/usr/bin/env python
"""Local Nexus-like knowledge compiler for Meta_workflow.

The implementation intentionally uses only the Python standard library so it can
run from the user's existing Anaconda base interpreter.
"""

from __future__ import annotations

import argparse
import csv
import contextlib
import hashlib
import html
import json
import math
import os
import random
import re
import sqlite3
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
KNOWLEDGE_DIR = SCRIPT_PATH.parents[1]
ROOT_DIR = SCRIPT_PATH.parents[3]
RUNTIME_DIR = KNOWLEDGE_DIR / "runtime"
DEFAULT_DB_PATH = RUNTIME_DIR / "knowledge.sqlite3"
SUITE_NAME = "meta_workflow_30"
SEC_SUITE_NAME = "sec_10k_150"
SEC_CORPUS_ID = "sec_10k_2022"
HF_SEC_CORPUS_ID = "sec_10k_hf_large"
KRAFT_PUBLIC_SUITE_NAME = "kraft_public_150"
KRAFT_PUBLIC_CORPUS_ID = "sec_10k_2022_kraft_public"
IKUN_SUITE_NAME = "ikunaim_90"
IKUN_ADAPTIVE_SUITE_NAME = "ikunaim_adaptive_40"
IKUN_SUITE_NAMES = {IKUN_SUITE_NAME, IKUN_ADAPTIVE_SUITE_NAME}
IKUN_CORPUS_ID = "ikunaim_full"
IKUN_DEFAULT_ROOT = Path(r"C:\Users\dzw\Desktop\ikunAim")
IKUN_TEXT_EXTENSIONS = {".md", ".yaml", ".yml", ".json", ".jsonl", ".txt", ".csv", ".pdf"}
IKUN_EXCLUDED_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules"}
IKUN_BINARY_EXTENSIONS = {
    ".exe",
    ".apk",
    ".7z",
    ".zip",
    ".mp4",
    ".sqlite",
    ".db",
    ".dll",
    ".bin",
    ".onnx",
    ".pt",
    ".pth",
    ".model",
}
IKUN_CONTEXTS = {
    "ikunaim_workflow": ["project_profile", "workflow_control", "role_gate"],
    "ikunaim_memory": ["memory_system"],
    "ikunaim_runs": ["run_history", "workflow_control"],
    "ikunaim_business": ["business_context", "project_profile"],
    "ikunaim_pro": ["pro_feedback", "workflow_control"],
}
SEC_RUNTIME_DIR = RUNTIME_DIR / SEC_CORPUS_ID
SEC_CONFIG_EXAMPLE = KNOWLEDGE_DIR / "config" / "sec_10k_2022.example.json"
SEC_CONFIG_LOCAL = KNOWLEDGE_DIR / "config" / "sec_10k_2022.local.json"
SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dash}/{primary_document}"
SP500_CURRENT_CONSTITUENTS_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
SEC_DEFAULT_RATE_PER_SECOND = 5
SEC_MAX_RATE_PER_SECOND = 10

OFFICIAL_PINECONE_KRAFT_METRICS = {
    "compiled": {"label": "Pinecone Nexus", "completion": 1.0, "latency_avg_s": 22.7, "accuracy": 0.680, "tokens_avg": 6733, "steps_avg": 1.69},
    "agentic_rag": {"label": "Agentic RAG", "completion": 0.987, "latency_avg_s": 37.9, "accuracy": 0.413, "tokens_avg": 49103, "steps_avg": 7.77},
    "coding_agent": {"label": "Coding agent", "completion": 0.627, "latency_avg_s": 84.1, "accuracy": 0.585, "tokens_avg": 528301, "steps_avg": 14.77},
}

SEC_METRIC_TAGS = {
    "revenue_usd": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
    "net_income_usd": ["NetIncomeLoss", "ProfitLoss"],
    "assets_usd": ["Assets"],
    "capex_usd": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "r_and_d_usd": ["ResearchAndDevelopmentExpense"],
    "share_repurchases_usd": ["PaymentsForRepurchaseOfCommonStock", "PaymentsForRepurchaseOfEquity"],
    "operating_cash_flow_usd": ["NetCashProvidedByUsedInOperatingActivities"],
}

SEC_FIELD_LABELS = {
    "revenue_usd": "revenue",
    "net_income_usd": "net income",
    "assets_usd": "assets",
    "capex_usd": "capital expenditures",
    "r_and_d_usd": "research and development expense",
    "share_repurchases_usd": "share repurchases",
    "operating_cash_flow_usd": "operating cash flow",
    "employees": "employees",
    "risk_factor_summary": "risk factors",
    "segments": "segments",
    "acquisitions": "acquisitions",
    "capex_to_revenue_ratio": "capex to revenue ratio",
    "net_income_margin": "net income margin",
    "revenue_to_assets_ratio": "revenue to assets ratio",
}

SEC_FALLBACK_TICKERS = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "GOOG", "META", "NVDA", "TSLA", "BRK-B", "JPM",
    "JNJ", "V", "PG", "UNH", "HD", "MA", "BAC", "XOM", "PFE", "KO",
    "PEP", "COST", "AVGO", "CSCO", "TMO", "ABBV", "WMT", "CRM", "MCD", "ABT",
    "ACN", "DHR", "LIN", "NKE", "DIS", "MRK", "TXN", "NEE", "VZ", "CMCSA",
    "ADBE", "NFLX", "QCOM", "AMD", "INTC", "IBM", "ORCL", "GE", "CAT", "BA",
    "HON", "AMGN", "LOW", "UPS", "RTX", "SBUX", "GS", "BLK", "AXP", "MS",
    "SPGI", "NOW", "INTU", "ISRG", "MDT", "LMT", "AMAT", "BKNG", "DE", "GILD",
    "ADP", "TJX", "SYK", "MDLZ", "CVS", "CI", "ELV", "MO", "DUK", "SO",
    "PLD", "CB", "MMC", "C", "SCHW", "USB", "PNC", "TGT", "CL", "BDX",
    "ZTS", "REGN", "VRTX", "ADI", "MU", "LRCX", "KLAC", "PANW", "SNPS", "CDNS",
]

TEXT_EXTENSIONS = {".md", ".yaml", ".yml", ".json", ".jsonl", ".txt"}
SOURCE_DIRS = [
    ROOT_DIR / "integrations" / "pro_bridge" / "protocols",
    ROOT_DIR / "integrations" / "pro_bridge" / "templates",
    ROOT_DIR / "integrations" / "pro_bridge" / "config",
]
SOURCE_FILES = [
    ROOT_DIR / "README.md",
    ROOT_DIR / "AGENTS.md",
    ROOT_DIR / "docs" / "architecture" / "vision.md",
    ROOT_DIR / "docs" / "methodology" / "map_methodology.md",
    ROOT_DIR / "integrations" / "pro_bridge" / "README.md",
]


class KnowledgeError(Exception):
    """Expected command failure that should be rendered as JSON."""


@dataclass(frozen=True)
class CitationSpec:
    field_path: str
    source_path: str
    needle: str
    confidence: float = 0.9


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_id(*parts: str, length: int = 16) -> str:
    raw = "::".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:length]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rel_path(path: Path) -> str:
    return path.resolve().relative_to(ROOT_DIR).as_posix()


def storage_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT_DIR).as_posix()
    except ValueError:
        return str(resolved)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9_./:-]+", text.lower())
    stop = {
        "the",
        "and",
        "or",
        "a",
        "an",
        "to",
        "of",
        "in",
        "for",
        "with",
        "is",
        "are",
        "what",
        "which",
        "how",
        "should",
        "does",
        "do",
        "be",
        "by",
        "as",
        "that",
        "this",
        "it",
        "its",
        "from",
    }
    return [word for word in words if len(word) > 1 and word not in stop]


def flatten_json(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        rows: list[tuple[str, Any]] = [(prefix, value)] if prefix else []
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(flatten_json(item, path))
        return rows
    if isinstance(value, list):
        rows = [(prefix, value)]
        for index, item in enumerate(value):
            path = f"{prefix}[{index}]" if prefix else f"[{index}]"
            rows.extend(flatten_json(item, path))
        return rows
    return [(prefix, value)]


def ensure_runtime() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    ensure_runtime()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sources (
          id TEXT PRIMARY KEY,
          path TEXT NOT NULL UNIQUE,
          content_hash TEXT NOT NULL,
          byte_count INTEGER NOT NULL,
          line_count INTEGER NOT NULL,
          content TEXT NOT NULL,
          indexed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS contexts (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          description TEXT NOT NULL,
          artifact_types_json TEXT NOT NULL,
          acl_tags_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS artifacts (
          id TEXT PRIMARY KEY,
          context_id TEXT NOT NULL,
          artifact_type TEXT NOT NULL,
          title TEXT NOT NULL,
          summary TEXT NOT NULL,
          data_json TEXT NOT NULL,
          confidence REAL NOT NULL,
          policy_tags_json TEXT NOT NULL,
          source_hashes_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(context_id) REFERENCES contexts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS citations (
          id TEXT PRIMARY KEY,
          artifact_id TEXT NOT NULL,
          field_path TEXT NOT NULL,
          source_id TEXT NOT NULL,
          path TEXT NOT NULL,
          line_start INTEGER NOT NULL,
          line_end INTEGER NOT NULL,
          quote TEXT NOT NULL,
          confidence REAL NOT NULL,
          FOREIGN KEY(artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE,
          FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS eval_cases (
          id TEXT PRIMARY KEY,
          suite TEXT NOT NULL,
          category TEXT NOT NULL,
          question TEXT NOT NULL,
          query_json TEXT NOT NULL,
          expected_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS eval_runs (
          id TEXT PRIMARY KEY,
          suite TEXT NOT NULL,
          retriever TEXT NOT NULL,
          case_id TEXT NOT NULL,
          passed INTEGER NOT NULL,
          score REAL NOT NULL,
          latency_ms REAL NOT NULL,
          source_bytes INTEGER NOT NULL,
          steps INTEGER NOT NULL,
          citation_coverage REAL NOT NULL,
          answer_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES eval_cases(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sec_filings (
          id TEXT PRIMARY KEY,
          corpus TEXT NOT NULL,
          ticker TEXT NOT NULL,
          cik TEXT NOT NULL,
          company TEXT NOT NULL,
          form TEXT NOT NULL,
          fiscal_year INTEGER NOT NULL,
          filing_date TEXT NOT NULL,
          report_date TEXT NOT NULL,
          accession TEXT NOT NULL,
          primary_document TEXT NOT NULL,
          document_url TEXT NOT NULL,
          local_raw_path TEXT NOT NULL,
          local_text_path TEXT NOT NULL,
          content_hash TEXT NOT NULL,
          raw_byte_count INTEGER NOT NULL,
          normalized_byte_count INTEGER NOT NULL,
          metadata_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sec_sections (
          id TEXT PRIMARY KEY,
          filing_id TEXT NOT NULL,
          section_key TEXT NOT NULL,
          heading TEXT NOT NULL,
          line_start INTEGER NOT NULL,
          line_end INTEGER NOT NULL,
          text_preview TEXT NOT NULL,
          FOREIGN KEY(filing_id) REFERENCES sec_filings(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sec_artifacts (
          id TEXT PRIMARY KEY,
          corpus TEXT NOT NULL,
          filing_id TEXT NOT NULL,
          ticker TEXT NOT NULL,
          cik TEXT NOT NULL,
          company TEXT NOT NULL,
          artifact_type TEXT NOT NULL,
          title TEXT NOT NULL,
          data_json TEXT NOT NULL,
          citations_json TEXT NOT NULL,
          confidence REAL NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(filing_id) REFERENCES sec_filings(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sec_chunks (
          id TEXT PRIMARY KEY,
          corpus TEXT NOT NULL,
          filing_id TEXT NOT NULL,
          ticker TEXT NOT NULL,
          company TEXT NOT NULL,
          chunk_index INTEGER NOT NULL,
          line_start INTEGER NOT NULL,
          line_end INTEGER NOT NULL,
          text TEXT NOT NULL,
          byte_count INTEGER NOT NULL,
          FOREIGN KEY(filing_id) REFERENCES sec_filings(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ikun_sources (
          id TEXT PRIMARY KEY,
          corpus TEXT NOT NULL,
          root_path TEXT NOT NULL,
          rel_path TEXT NOT NULL,
          suffix TEXT NOT NULL,
          content_hash TEXT NOT NULL,
          byte_count INTEGER NOT NULL,
          line_count INTEGER NOT NULL,
          content TEXT NOT NULL,
          encoding TEXT NOT NULL,
          noisy INTEGER NOT NULL,
          warnings_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(corpus, rel_path)
        );

        CREATE TABLE IF NOT EXISTS ikun_artifacts (
          id TEXT PRIMARY KEY,
          corpus TEXT NOT NULL,
          context_id TEXT NOT NULL,
          artifact_type TEXT NOT NULL,
          title TEXT NOT NULL,
          data_json TEXT NOT NULL,
          citations_json TEXT NOT NULL,
          confidence REAL NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ikun_chunks (
          id TEXT PRIMARY KEY,
          corpus TEXT NOT NULL,
          source_id TEXT NOT NULL,
          rel_path TEXT NOT NULL,
          chunk_index INTEGER NOT NULL,
          line_start INTEGER NOT NULL,
          line_end INTEGER NOT NULL,
          text TEXT NOT NULL,
          byte_count INTEGER NOT NULL,
          FOREIGN KEY(source_id) REFERENCES ikun_sources(id) ON DELETE CASCADE
        );
        """
    )
    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS source_fts "
            "USING fts5(source_id UNINDEXED, path, content)"
        )
    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS sec_chunk_fts "
            "USING fts5(chunk_id UNINDEXED, corpus UNINDEXED, ticker, company, text)"
        )
    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS ikun_chunk_fts "
            "USING fts5(chunk_id UNINDEXED, corpus UNINDEXED, rel_path, text)"
        )
    conn.commit()


def discover_sources() -> list[Path]:
    paths: set[Path] = set()
    for path in SOURCE_FILES:
        if path.exists():
            paths.add(path.resolve())
    for source_dir in SOURCE_DIRS:
        if not source_dir.exists():
            continue
        for path in source_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
                paths.add(path.resolve())
    return sorted(paths, key=lambda item: rel_path(item))


def ingest_sources(conn: sqlite3.Connection) -> dict[str, Any]:
    init_schema(conn)
    rows = []
    now = utc_now()
    for path in discover_sources():
        text = read_text(path)
        path_rel = rel_path(path)
        source_id = stable_id(path_rel)
        rows.append(
            {
                "id": source_id,
                "path": path_rel,
                "content_hash": sha256_text(text),
                "byte_count": len(text.encode("utf-8")),
                "line_count": len(text.splitlines()),
                "content": text,
                "indexed_at": now,
            }
        )
    with conn:
        for row in rows:
            conn.execute(
                """
                INSERT INTO sources (id, path, content_hash, byte_count, line_count, content, indexed_at)
                VALUES (:id, :path, :content_hash, :byte_count, :line_count, :content, :indexed_at)
                ON CONFLICT(path) DO UPDATE SET
                  content_hash = excluded.content_hash,
                  byte_count = excluded.byte_count,
                  line_count = excluded.line_count,
                  content = excluded.content,
                  indexed_at = excluded.indexed_at
                """,
                row,
            )
        with contextlib.suppress(sqlite3.OperationalError):
            conn.execute("DELETE FROM source_fts")
            conn.executemany(
                "INSERT INTO source_fts (source_id, path, content) VALUES (:id, :path, :content)",
                rows,
            )
    return {"status": "ingested", "source_count": len(rows)}


def get_source(conn: sqlite3.Connection, source_path: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM sources WHERE path = ?", (source_path,)).fetchone()
    if row is None:
        raise KnowledgeError(f"source not ingested: {source_path}")
    return row


def find_line_range(content: str, needle: str) -> tuple[int, int, str]:
    lines = content.splitlines()
    needle_clean = " ".join(needle.split())
    if not needle_clean:
        return 1, 1, ""

    for index, line in enumerate(lines, start=1):
        if needle_clean.lower() in " ".join(line.split()).lower():
            return index, index, line.strip()

    window = []
    for start in range(0, max(0, len(lines) - 2)):
        joined = " ".join(line.strip() for line in lines[start : start + 3])
        window.append((start + 1, joined))
    for start, joined in window:
        if needle_clean.lower() in " ".join(joined.split()).lower():
            return start, min(start + 2, len(lines)), joined.strip()

    tokens = tokenize(needle_clean)
    best = (0, 1, lines[0].strip() if lines else "")
    for index, line in enumerate(lines, start=1):
        score = sum(1 for token in tokens if token in line.lower())
        if score > best[0]:
            best = (score, index, line.strip())
    return best[1], best[1], best[2]


def sec_paths(corpus: str = SEC_CORPUS_ID) -> dict[str, Path]:
    base = RUNTIME_DIR / corpus
    return {
        "base": base,
        "raw": base / "raw",
        "submissions": base / "raw" / "submissions",
        "companyfacts": base / "raw" / "companyfacts",
        "filings": base / "raw" / "filings",
        "normalized": base / "normalized",
        "judge": base / "judge",
        "manifest": base / "manifest.jsonl",
        "ticker_manifest": base / "ticker_manifest.json",
        "manifest_audit": base / "manifest_audit.json",
        "groundtruth": base / "groundtruth_150.locked.jsonl",
        "agent_pack": base / "agent_pack.jsonl",
        "agent_answers": base / "agent_answers.jsonl",
        "agent_answers_draft": base / "agent_answers.draft.jsonl",
        "judge_pack_blind": base / "judge_pack.blind.jsonl",
        "judge_answer_key": base / "judge_answer_key.json",
        "judge_results": base / "judge_results.jsonl",
        "judge_summary": base / "judge_summary.json",
        "kraft_report": base / "kraft_comparison_report.md",
        "official_delta": base / "official_delta_table.json",
    }


def ensure_sec_runtime(corpus: str = SEC_CORPUS_ID) -> dict[str, Path]:
    paths = sec_paths(corpus)
    for key in ["raw", "submissions", "companyfacts", "filings", "normalized", "judge"]:
        paths[key].mkdir(parents=True, exist_ok=True)
    return paths


def load_json_file(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))


def write_json_file(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def fetch_text_url(url: str, timeout: int = 60) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Meta_workflow KRAFT public replication"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8-sig", errors="replace")


def read_csv_rows_from_text(text: str) -> list[dict[str, str]]:
    return [dict(row) for row in csv.DictReader(text.splitlines())]


def load_sec_config(config_path: Path, require_user_agent: bool = False) -> dict[str, Any]:
    if not config_path.exists():
        if require_user_agent:
            raise KnowledgeError(
                "SEC config missing. Copy integrations/knowledge/config/sec_10k_2022.example.json "
                "to integrations/knowledge/config/sec_10k_2022.local.json and set sec_user_agent."
            )
        return {}
    config = load_json_file(config_path, {})
    if require_user_agent:
        user_agent = str(config.get("sec_user_agent", "")).strip()
        if not user_agent or "contact@example.com" in user_agent:
            raise KnowledgeError("SEC sec_user_agent must be set to a descriptive app/contact string.")
    rate = float(config.get("request_rate_per_second", SEC_DEFAULT_RATE_PER_SECOND))
    if rate <= 0 or rate > SEC_MAX_RATE_PER_SECOND:
        raise KnowledgeError(f"request_rate_per_second must be between 0 and {SEC_MAX_RATE_PER_SECOND}.")
    return config


class SecRateLimiter:
    def __init__(self, requests_per_second: float) -> None:
        self.delay = 1.0 / max(0.1, requests_per_second)
        self.last_at = 0.0

    def wait(self) -> None:
        now = time.perf_counter()
        remaining = self.delay - (now - self.last_at)
        if remaining > 0:
            time.sleep(remaining)
        self.last_at = time.perf_counter()


def sec_request(url: str, user_agent: str, rate_limiter: SecRateLimiter, timeout: int = 60) -> bytes:
    rate_limiter.wait()
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept-Encoding": "identity",
            "Accept": "application/json,text/html,text/plain,*/*",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise KnowledgeError(f"SEC request failed {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise KnowledgeError(f"SEC request failed for {url}: {exc.reason}") from exc


def sec_request_json(url: str, user_agent: str, rate_limiter: SecRateLimiter) -> Any:
    return json.loads(sec_request(url, user_agent, rate_limiter).decode("utf-8", errors="replace"))


def cik10(value: Any) -> str:
    return str(value).strip().lstrip("0").zfill(10)


def cik_int(value: Any) -> str:
    stripped = str(value).strip().lstrip("0")
    return stripped or "0"


def accession_no_dash(accession: str) -> str:
    return accession.replace("-", "")


def load_or_download_company_tickers(paths: dict[str, Path], config: dict[str, Any], limiter: SecRateLimiter) -> dict[str, Any]:
    path = paths["raw"] / "company_tickers.json"
    if path.exists():
        return load_json_file(path, {})
    data = sec_request_json(SEC_COMPANY_TICKERS_URL, config["sec_user_agent"], limiter)
    write_json_file(path, data)
    return data


def company_ticker_map(company_tickers: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for item in company_tickers.values():
        ticker = str(item.get("ticker", "")).upper()
        if not ticker:
            continue
        mapping[ticker] = {
            "ticker": ticker,
            "cik": cik10(item.get("cik_str", "")),
            "company": str(item.get("title", ticker)),
        }
    return mapping


def select_sec_companies(company_tickers: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    mapping = company_ticker_map(company_tickers)
    max_filings = int(config.get("max_filings", 493))
    requested = [str(ticker).upper() for ticker in config.get("tickers", []) if str(ticker).strip()]
    selected: list[dict[str, Any]] = []
    if requested:
        for ticker in requested:
            if ticker in mapping:
                selected.append(mapping[ticker])
        return selected[:max_filings]

    source = config.get("ticker_source", "sec_company_tickers_order")
    if source == "fallback_large_cap_manifest":
        for ticker in SEC_FALLBACK_TICKERS:
            if ticker in mapping:
                selected.append(mapping[ticker])
    else:
        for item in company_tickers.values():
            ticker = str(item.get("ticker", "")).upper()
            if ticker:
                selected.append({"ticker": ticker, "cik": cik10(item.get("cik_str", "")), "company": str(item.get("title", ticker))})
    return selected[:max_filings]


def normalize_ticker(value: str) -> str:
    return str(value).strip().upper().replace(".", "-")


def public_sp500_rows(args: argparse.Namespace) -> tuple[list[dict[str, str]], str, list[str]]:
    warnings: list[str] = []
    if getattr(args, "manifest_file", ""):
        path = Path(args.manifest_file)
        if not path.exists():
            raise KnowledgeError(f"S&P manifest file not found: {path}")
        return read_csv_rows_from_text(path.read_text(encoding="utf-8-sig", errors="replace")), str(path), warnings
    url = getattr(args, "manifest_url", "") or SP500_CURRENT_CONSTITUENTS_URL
    try:
        rows = read_csv_rows_from_text(fetch_text_url(url))
        if url == SP500_CURRENT_CONSTITUENTS_URL:
            warnings.append("using_current_sp500_constituents_not_historical_2022_membership")
        return rows, url, warnings
    except Exception as exc:
        warnings.append(f"public_manifest_download_failed:{exc}")
        return [{"Symbol": ticker, "Security": ticker, "GICS Sector": "", "CIK": ""} for ticker in SEC_FALLBACK_TICKERS], "fallback_large_cap_manifest", warnings


def sec_manifest_build(args: argparse.Namespace) -> dict[str, Any]:
    paths = ensure_sec_runtime(args.corpus)
    target = int(args.target_filings)
    rows, source, warnings = public_sp500_rows(args)
    companies = []
    seen: set[str] = set()
    as_of = str(args.as_of)
    for row in rows:
        ticker = normalize_ticker(row.get("Symbol") or row.get("symbol") or row.get("Ticker") or row.get("ticker") or "")
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        cik_value = row.get("CIK") or row.get("cik") or row.get("cik_str") or ""
        company = row.get("Security") or row.get("security") or row.get("Name") or row.get("name") or ticker
        sector = row.get("GICS Sector") or row.get("sector") or ""
        companies.append(
            {
                "ticker": ticker,
                "cik": cik10(cik_value) if cik_value else "",
                "company": company,
                "sector": sector,
                "as_of": as_of,
                "manifest_source": source,
            }
        )
        if len(companies) >= target:
            break
    missing_cik = [item["ticker"] for item in companies if not item["cik"]]
    if missing_cik:
        warnings.append(f"missing_cik_count:{len(missing_cik)}")
    manifest = {
        "created_at": utc_now(),
        "corpus": args.corpus,
        "as_of": as_of,
        "target_filings": target,
        "manifest_source": source,
        "companies": companies,
        "warnings": warnings,
    }
    write_json_file(paths["ticker_manifest"], manifest)
    audit = {
        "status": "manifest_built",
        "corpus": args.corpus,
        "as_of": as_of,
        "target_filings": target,
        "manifest_source": source,
        "public_sp500_manifest": source != "fallback_large_cap_manifest",
        "companies": len(companies),
        "missing_cik_count": len(missing_cik),
        "warnings": warnings,
        "corpus_gate": {
            "target_manifest_size_met": len(companies) >= min(490, target),
            "cik_coverage_met": len(missing_cik) == 0,
            "official_download_complete": False,
            "normalized_size_met": False,
            "fiscal_2022_match_met": False,
        },
    }
    write_json_file(paths["manifest_audit"], audit)
    return {
        "status": "sec_manifest_built",
        "corpus": args.corpus,
        "ticker_manifest_path": str(paths["ticker_manifest"]),
        "manifest_audit_path": str(paths["manifest_audit"]),
        "companies": len(companies),
        "missing_cik_count": len(missing_cik),
        "warnings": warnings,
    }


def find_annual_10k(submission: dict[str, Any], year: int) -> dict[str, Any] | None:
    recent = submission.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    company = str(submission.get("name", ""))

    candidates = []
    for index, form in enumerate(forms):
        form = str(form)
        if form not in {"10-K", "10-K/A"}:
            continue
        accession = accessions[index] if index < len(accessions) else ""
        primary = primary_docs[index] if index < len(primary_docs) else ""
        filing_date = filing_dates[index] if index < len(filing_dates) else ""
        report_date = report_dates[index] if index < len(report_dates) else ""
        if not accession or not primary:
            continue
        score = 0
        if report_date.startswith(str(year)):
            score += 4
        if filing_date.startswith(str(year + 1)):
            score += 2
        if filing_date.startswith(str(year)):
            score += 1
        if score == 0:
            continue
        candidates.append(
            {
                "form": form,
                "accession": accession,
                "primary_document": primary,
                "filing_date": filing_date,
                "report_date": report_date,
                "company": company,
                "score": score,
            }
        )
    candidates.sort(key=lambda item: (item["score"], item["filing_date"]), reverse=True)
    return candidates[0] if candidates else None


def sec_safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def sec_document_url(cik: str, accession: str, primary_document: str) -> str:
    return SEC_ARCHIVES_URL.format(
        cik_int=cik_int(cik),
        accession_no_dash=accession_no_dash(accession),
        primary_document=primary_document,
    )


def audit_sec_corpus(corpus: str, target_filings: int = 493, target_mb: int = 245) -> dict[str, Any]:
    paths = ensure_sec_runtime(corpus)
    ticker_manifest = load_json_file(paths["ticker_manifest"], {})
    manifest_rows = read_jsonl(paths["manifest"])
    target_min_mb = target_mb - 10
    target_max_mb = target_mb + 10
    missing_tickers = []
    duplicate_tickers = []
    non_2022 = []
    hash_drift = []
    raw_missing = []
    seen: set[str] = set()
    target_companies = ticker_manifest.get("companies", [])
    downloaded_tickers = {row.get("ticker") for row in manifest_rows}
    for company in target_companies:
        ticker = company.get("ticker")
        if ticker and ticker not in downloaded_tickers:
            missing_tickers.append(ticker)
    for row in manifest_rows:
        ticker = row.get("ticker", "")
        if ticker in seen:
            duplicate_tickers.append(ticker)
        seen.add(ticker)
        if str(row.get("report_date", "")).startswith("2022") or int(row.get("year", 0) or 0) == 2022:
            pass
        else:
            non_2022.append(ticker)
        raw_value = row.get("local_raw_path", "")
        raw_path = ROOT_DIR / raw_value if raw_value and not Path(raw_value).is_absolute() else Path(raw_value)
        if raw_value and raw_path.exists():
            if int(row.get("raw_byte_count", 0) or 0) and raw_path.stat().st_size != int(row.get("raw_byte_count", 0)):
                hash_drift.append(ticker)
        else:
            raw_missing.append(ticker)
    normalized_bytes = 0
    with contextlib.suppress(Exception):
        with connect() as conn:
            init_schema(conn)
            normalized_bytes = conn.execute("SELECT COALESCE(SUM(normalized_byte_count), 0) AS n FROM sec_filings WHERE corpus = ?", (corpus,)).fetchone()["n"]
    normalized_mb = normalized_bytes / (1024 * 1024)
    official_complete = len(manifest_rows) >= min(490, target_filings)
    fiscal_match = (len(manifest_rows) - len(non_2022)) / max(1, len(manifest_rows))
    audit = {
        "status": "audited",
        "corpus": corpus,
        "created_at": utc_now(),
        "target_filings": target_filings,
        "target_normalized_mb": target_mb,
        "ticker_manifest_companies": len(target_companies),
        "downloaded_filings": len(manifest_rows),
        "normalized_mb": round(normalized_mb, 3),
        "missing_tickers": missing_tickers,
        "duplicate_tickers": duplicate_tickers,
        "non_2022_filing_tickers": non_2022,
        "raw_missing_tickers": raw_missing,
        "hash_drift_tickers": hash_drift,
        "download_source": "SEC EDGAR Archives" if manifest_rows else "none",
        "blocked_official_download": False,
        "corpus_gate": {
            "official_download_complete": official_complete,
            "fiscal_2022_match_rate": round(fiscal_match, 4),
            "fiscal_2022_match_met": fiscal_match >= 0.95 and bool(manifest_rows),
            "normalized_size_met": target_min_mb <= normalized_mb <= target_max_mb,
            "source_url_hash_present": all(row.get("document_url") and row.get("raw_byte_count") for row in manifest_rows),
            "missing_ticker_count": len(missing_tickers),
        },
    }
    write_json_file(paths["manifest_audit"], audit)
    return audit


def write_blocked_sec_audit(corpus: str, error: str, target_filings: int = 493, target_mb: int = 245) -> dict[str, Any]:
    paths = ensure_sec_runtime(corpus)
    audit = audit_sec_corpus(corpus, target_filings, target_mb)
    audit.update(
        {
            "status": "blocked_official_download",
            "blocked_official_download": True,
            "block_reason": error,
            "disclaimer": "This corpus cannot be described as an official KRAFTBench-style reproduction until SEC 2022 filings are downloaded and audited.",
        }
    )
    write_json_file(paths["manifest_audit"], audit)
    return audit


HF_SECTION_TITLES = {
    "section_1": "Item 1. Business",
    "section_1A": "Item 1A. Risk Factors",
    "section_1B": "Item 1B. Unresolved Staff Comments",
    "section_2": "Item 2. Properties",
    "section_3": "Item 3. Legal Proceedings",
    "section_4": "Item 4. Mine Safety Disclosures",
    "section_5": "Item 5. Market for Registrant's Common Equity",
    "section_6": "Item 6. Selected Financial Data",
    "section_7": "Item 7. Management's Discussion and Analysis",
    "section_7A": "Item 7A. Quantitative and Qualitative Disclosures About Market Risk",
    "section_8": "Item 8. Financial Statements and Supplementary Data",
    "section_9": "Item 9. Changes in and Disagreements With Accountants",
    "section_9A": "Item 9A. Controls and Procedures",
    "section_9B": "Item 9B. Other Information",
    "section_10": "Item 10. Directors, Executive Officers and Corporate Governance",
    "section_11": "Item 11. Executive Compensation",
    "section_12": "Item 12. Security Ownership of Certain Beneficial Owners and Management",
    "section_13": "Item 13. Certain Relationships and Related Transactions",
    "section_14": "Item 14. Principal Accountant Fees and Services",
    "section_15": "Item 15. Exhibits and Financial Statement Schedules",
}


def hf_section_sort_key(section_key: str) -> tuple[int, str]:
    match = re.match(r"section_(\d+)([A-Z]?)$", section_key)
    if not match:
        return (999, section_key)
    suffix = match.group(2)
    return (int(match.group(1)) * 10 + (ord(suffix) - ord("A") + 1 if suffix else 0), suffix)


def hf_report_to_text(report: dict[str, Any]) -> str:
    lines: list[str] = []
    for section_key in sorted(report, key=hf_section_sort_key):
        title = HF_SECTION_TITLES.get(section_key, section_key)
        values = report.get(section_key) or []
        paragraphs = values if isinstance(values, list) else [values]
        lines.append(title)
        for paragraph in paragraphs:
            clean = re.sub(r"\s+", " ", str(paragraph)).strip()
            if clean and clean.lower() != title.lower():
                lines.append(clean)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def hf_report_text_bytes(report: dict[str, Any]) -> int:
    return len(hf_report_to_text(report).encode("utf-8"))


def hf_filing_sort_key(filing: dict[str, Any]) -> tuple[str, str]:
    return (str(filing.get("filingDate", "")), str(filing.get("reportDate", "")))


def hf_iter_company_records(source_dir: Path) -> list[tuple[Path, int, dict[str, Any]]]:
    rows: list[tuple[Path, int, dict[str, Any]]] = []
    for path in sorted(source_dir.glob("*.jsonl")):
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_no, line in enumerate(handle, start=1):
                if line.strip():
                    rows.append((path, line_no, json.loads(line)))
    return rows


def clear_sec_corpus(conn: sqlite3.Connection, corpus: str) -> None:
    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute("DELETE FROM sec_chunk_fts WHERE corpus = ?", (corpus,))
    conn.execute("DELETE FROM sec_chunks WHERE corpus = ?", (corpus,))
    conn.execute("DELETE FROM sec_artifacts WHERE corpus = ?", (corpus,))
    conn.execute(
        "DELETE FROM sec_sections WHERE filing_id IN (SELECT id FROM sec_filings WHERE corpus = ?)",
        (corpus,),
    )
    conn.execute("DELETE FROM sec_filings WHERE corpus = ?", (corpus,))


def sec_insert_normalized_filing(conn: sqlite3.Connection, row: dict[str, Any], text: str) -> None:
    filing_id = row["filing_id"]
    conn.execute(
        """
        INSERT INTO sec_filings
          (id, corpus, ticker, cik, company, form, fiscal_year, filing_date, report_date,
           accession, primary_document, document_url, local_raw_path, local_text_path,
           content_hash, raw_byte_count, normalized_byte_count, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          local_text_path = excluded.local_text_path,
          content_hash = excluded.content_hash,
          raw_byte_count = excluded.raw_byte_count,
          normalized_byte_count = excluded.normalized_byte_count,
          metadata_json = excluded.metadata_json,
          created_at = excluded.created_at
        """,
        (
            filing_id,
            row["corpus"],
            row["ticker"],
            row["cik"],
            row["company"],
            row["form"],
            int(row["year"]),
            row["filing_date"],
            row["report_date"],
            row["accession"],
            row["primary_document"],
            row["document_url"],
            row["local_raw_path"],
            row["local_text_path"],
            sha256_text(text),
            int(row["raw_byte_count"]),
            len(text.encode("utf-8")),
            json_dumps(row["metadata"]),
            utc_now(),
        ),
    )
    conn.execute("DELETE FROM sec_sections WHERE filing_id = ?", (filing_id,))
    for section in extract_sec_sections(text):
        conn.execute(
            """
            INSERT INTO sec_sections
              (id, filing_id, section_key, heading, line_start, line_end, text_preview)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stable_id(filing_id, section["section_key"], str(section["line_start"]), length=24),
                filing_id,
                section["section_key"],
                section["heading"],
                section["line_start"],
                section["line_end"],
                section["text_preview"],
            ),
        )


def sec_import_hf(args: argparse.Namespace) -> dict[str, Any]:
    paths = ensure_sec_runtime(args.corpus)
    source_dir = Path(args.source_dir) if args.source_dir else sec_paths(SEC_CORPUS_ID)["raw"] / "hf_financial_reports_sec_large_test"
    if not source_dir.exists():
        raise KnowledgeError(f"HF SEC source directory not found: {source_dir}")
    target_min_bytes = int(float(args.target_min_mb) * 1024 * 1024)
    target_max_bytes = int(float(args.target_max_mb) * 1024 * 1024)
    max_filings = int(args.max_filings or 0)

    candidates: list[dict[str, Any]] = []
    company_records = hf_iter_company_records(source_dir)
    for source_path, line_no, company in company_records:
        filings = [item for item in company.get("filings", []) if str(item.get("form", "")) == "10-K" and item.get("report")]
        if not filings:
            continue
        latest = max(filings, key=hf_filing_sort_key)
        ticker_values = company.get("tickers") or []
        ticker = sec_safe_name(str(ticker_values[0] if ticker_values else company.get("cik", "UNKNOWN")).upper())
        cik = cik10(company.get("cik", ""))
        for filing_index, filing in enumerate(filings):
            report = filing.get("report") or {}
            report_date = str(filing.get("reportDate") or filing.get("filingDate") or "")
            filing_date = str(filing.get("filingDate") or report_date)
            year = int((report_date or filing_date or "0")[:4] or 0)
            accession = stable_id(args.corpus, cik, filing_date, report_date, str(filing_index), length=20)
            text_bytes = hf_report_text_bytes(report)
            candidates.append(
                {
                    "priority": 0 if filing is latest else 1,
                    "sort_key": (0 if filing is latest else 1, ticker, filing_date, report_date),
                    "source_path": source_path,
                    "source_line": line_no,
                    "company_record": company,
                    "filing": filing,
                    "ticker": ticker,
                    "cik": cik,
                    "company": str(company.get("name") or ticker),
                    "year": year,
                    "filing_date": filing_date,
                    "report_date": report_date,
                    "accession": f"hf-{accession}",
                    "text_bytes": text_bytes,
                    "is_latest_company_filing": filing is latest,
                }
            )

    selected: list[dict[str, Any]] = []
    total_bytes = 0
    for candidate in sorted(candidates, key=lambda item: item["sort_key"]):
        if max_filings and len(selected) >= max_filings:
            break
        next_bytes = total_bytes + int(candidate["text_bytes"])
        if selected and next_bytes > target_max_bytes and total_bytes >= target_min_bytes:
            continue
        selected.append(candidate)
        total_bytes = next_bytes
        if max_filings and len(selected) >= max_filings:
            break
        if total_bytes >= target_min_bytes and (not max_filings):
            if total_bytes >= target_max_bytes:
                break

    if not selected:
        raise KnowledgeError(f"No HF 10-K filings found under {source_dir}")

    manifest_rows: list[dict[str, Any]] = []
    with connect(Path(args.db)) as conn:
        init_schema(conn)
        with conn:
            clear_sec_corpus(conn, args.corpus)
            for candidate in selected:
                text = hf_report_to_text(candidate["filing"].get("report") or {})
                text_name = f"{candidate['ticker']}_{candidate['accession']}.txt"
                text_path = paths["normalized"] / text_name
                text_path.write_text(text, encoding="utf-8")
                row = {
                    "corpus": args.corpus,
                    "filing_id": stable_id(args.corpus, candidate["ticker"], candidate["accession"], length=24),
                    "ticker": candidate["ticker"],
                    "cik": candidate["cik"],
                    "company": candidate["company"],
                    "year": candidate["year"],
                    "form": "10-K",
                    "filing_date": candidate["filing_date"],
                    "report_date": candidate["report_date"],
                    "accession": candidate["accession"],
                    "primary_document": "hf-jsonl-report",
                    "document_url": f"hf://JanosAudran/financial-reports-sec/{candidate['source_path'].name}#L{candidate['source_line']}",
                    "local_raw_path": storage_path(candidate["source_path"]),
                    "local_text_path": storage_path(text_path),
                    "raw_byte_count": candidate["source_path"].stat().st_size,
                    "metadata": {
                        "source": "huggingface:JanosAudran/financial-reports-sec",
                        "source_line": candidate["source_line"],
                        "entity_type": candidate["company_record"].get("entityType", ""),
                        "sic": candidate["company_record"].get("sic", ""),
                        "exchanges": candidate["company_record"].get("exchanges", []),
                        "tickers": candidate["company_record"].get("tickers", []),
                        "is_latest_company_filing": candidate["is_latest_company_filing"],
                        "labels": candidate["filing"].get("labels", {}),
                        "returns": candidate["filing"].get("returns", {}),
                        "local_companyfacts_path": "",
                    },
                }
                sec_insert_normalized_filing(conn, row, text)
                manifest_rows.append({key: value for key, value in row.items() if key not in {"metadata"}} | {"metadata": row["metadata"]})

    paths["manifest"].write_text("", encoding="utf-8")
    append_jsonl(paths["manifest"], manifest_rows)
    years = Counter(str(row["year"]) for row in manifest_rows)
    latest_count = sum(1 for row in manifest_rows if row["metadata"].get("is_latest_company_filing"))
    return {
        "status": "sec_hf_imported",
        "corpus": args.corpus,
        "source_dir": str(source_dir),
        "companies_seen": len(company_records),
        "candidate_filings": len(candidates),
        "imported_filings": len(manifest_rows),
        "latest_company_filings": latest_count,
        "normalized_bytes": total_bytes,
        "normalized_mib": round(total_bytes / (1024 * 1024), 3),
        "target_min_mib": args.target_min_mb,
        "target_max_mib": args.target_max_mb,
        "year_distribution": dict(sorted(years.items())),
        "manifest_path": str(paths["manifest"]),
    }


def sec_download(args: argparse.Namespace) -> dict[str, Any]:
    config_path = Path(args.config or SEC_CONFIG_LOCAL)
    config = load_sec_config(config_path, require_user_agent=True)
    paths = ensure_sec_runtime(args.corpus)
    year = int(config.get("year", 2022))
    max_filings = min(int(args.max_filings or config.get("max_filings", 493)), int(config.get("max_filings", 493)))
    limiter = SecRateLimiter(float(config.get("request_rate_per_second", SEC_DEFAULT_RATE_PER_SECOND)))
    ticker_manifest = load_json_file(paths["ticker_manifest"], {})
    if ticker_manifest.get("companies"):
        companies = ticker_manifest["companies"][:max_filings]
    else:
        company_tickers = load_or_download_company_tickers(paths, config, limiter)
        companies = select_sec_companies(company_tickers, {**config, "max_filings": max_filings})
        write_json_file(paths["ticker_manifest"], {"created_at": utc_now(), "year": year, "companies": companies})

    manifest_rows: list[dict[str, Any]] = []
    downloaded = 0
    skipped = 0
    for company in companies:
        ticker = company["ticker"]
        cik = company["cik"]
        submission_path = paths["submissions"] / f"CIK{cik}.json"
        if submission_path.exists() and not args.refresh:
            submission = load_json_file(submission_path, {})
        else:
            submission = sec_request_json(SEC_SUBMISSIONS_URL.format(cik=cik), config["sec_user_agent"], limiter)
            write_json_file(submission_path, submission)

        annual = find_annual_10k(submission, year)
        if not annual:
            skipped += 1
            continue

        facts_path = paths["companyfacts"] / f"CIK{cik}.json"
        if not facts_path.exists() or args.refresh:
            with contextlib.suppress(KnowledgeError):
                facts = sec_request_json(SEC_COMPANYFACTS_URL.format(cik=cik), config["sec_user_agent"], limiter)
                write_json_file(facts_path, facts)

        document_url = sec_document_url(cik, annual["accession"], annual["primary_document"])
        raw_name = f"{ticker}_{annual['accession']}_{sec_safe_name(annual['primary_document'])}"
        raw_path = paths["filings"] / raw_name
        if not raw_path.exists() or args.refresh:
            raw_bytes = sec_request(document_url, config["sec_user_agent"], limiter)
            raw_path.write_bytes(raw_bytes)
        raw_size = raw_path.stat().st_size
        manifest_rows.append(
            {
                "corpus": args.corpus,
                "ticker": ticker,
                "cik": cik,
                "company": company.get("company") or annual.get("company") or ticker,
                "year": year,
                "form": annual["form"],
                "filing_date": annual["filing_date"],
                "report_date": annual["report_date"],
                "accession": annual["accession"],
                "primary_document": annual["primary_document"],
                "document_url": document_url,
                "local_raw_path": rel_path(raw_path),
                "local_companyfacts_path": rel_path(facts_path) if facts_path.exists() else "",
                "raw_byte_count": raw_size,
                "created_at": utc_now(),
            }
        )
        downloaded += 1
        if downloaded >= max_filings:
            break

    paths["manifest"].write_text("", encoding="utf-8")
    append_jsonl(paths["manifest"], manifest_rows)
    audit = audit_sec_corpus(args.corpus, max_filings, int(config.get("target_normalized_mb", 245))) if getattr(args, "audit", False) else {}
    return {
        "status": "sec_downloaded",
        "corpus": args.corpus,
        "year": year,
        "manifest_path": str(paths["manifest"]),
        "ticker_manifest_path": str(paths["ticker_manifest"]),
        "downloaded_filings": downloaded,
        "skipped_without_10k": skipped,
        "raw_bytes": sum(row["raw_byte_count"] for row in manifest_rows),
        "manifest_audit_path": str(paths["manifest_audit"]) if audit else "",
    }


def strip_sec_html(raw: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>", " ", raw)
    text = re.sub(r"(?is)<style.*?</style>", " ", text)
    text = re.sub(r"(?is)<SEC-HEADER>.*?</SEC-HEADER>", " ", text)
    text = re.sub(r"(?is)<TYPE>GRAPHIC.*?(?=<TYPE>|</DOCUMENT>|$)", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    lines = []
    for line in text.splitlines():
        clean = line.strip()
        if clean:
            lines.append(clean)
    return "\n".join(lines) + "\n"


SEC_SECTION_PATTERNS = {
    "business": re.compile(r"\bitem\s+1[.\s-]+business\b", re.I),
    "risk_factors": re.compile(r"\bitem\s+1a[.\s-]+risk\s+factors\b", re.I),
    "properties": re.compile(r"\bitem\s+2[.\s-]+properties\b", re.I),
    "mda": re.compile(r"\bitem\s+7[.\s-]+management", re.I),
    "financial_statements": re.compile(r"\bitem\s+8[.\s-]+financial", re.I),
}


def extract_sec_sections(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    starts = []
    seen: set[str] = set()
    for index, line in enumerate(lines, start=1):
        normalized = re.sub(r"\s+", " ", line).strip()
        if len(normalized) > 160:
            continue
        for key, pattern in SEC_SECTION_PATTERNS.items():
            if key not in seen and pattern.search(normalized):
                starts.append({"section_key": key, "heading": normalized, "line_start": index})
                seen.add(key)
    starts.sort(key=lambda item: item["line_start"])
    sections = []
    for pos, item in enumerate(starts):
        end = starts[pos + 1]["line_start"] - 1 if pos + 1 < len(starts) else min(item["line_start"] + 400, len(lines))
        preview = " ".join(lines[item["line_start"] - 1 : min(end, item["line_start"] + 20)])
        sections.append({**item, "line_end": max(item["line_start"], end), "text_preview": preview[:1200]})
    return sections


def sec_normalize(args: argparse.Namespace) -> dict[str, Any]:
    paths = ensure_sec_runtime(args.corpus)
    rows = read_jsonl(paths["manifest"])
    if not rows:
        raise KnowledgeError(f"SEC manifest missing or empty: {paths['manifest']}. Run sec-download first.")
    total_bytes = 0
    normalized_rows = []
    with connect(Path(args.db)) as conn:
        init_schema(conn)
        with conn:
            for row in rows:
                raw_path = ROOT_DIR / row["local_raw_path"]
                if not raw_path.exists():
                    continue
                normalized = strip_sec_html(raw_path.read_text(encoding="utf-8", errors="replace"))
                text_path = paths["normalized"] / f"{row['ticker']}_{row['accession']}.txt"
                text_path.write_text(normalized, encoding="utf-8")
                text_bytes = len(normalized.encode("utf-8"))
                total_bytes += text_bytes
                filing_id = stable_id(args.corpus, row["ticker"], row["accession"], length=24)
                metadata = {key: value for key, value in row.items() if key not in {"local_raw_path"}}
                conn.execute(
                    """
                    INSERT INTO sec_filings
                      (id, corpus, ticker, cik, company, form, fiscal_year, filing_date, report_date,
                       accession, primary_document, document_url, local_raw_path, local_text_path,
                       content_hash, raw_byte_count, normalized_byte_count, metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                      local_text_path = excluded.local_text_path,
                      content_hash = excluded.content_hash,
                      raw_byte_count = excluded.raw_byte_count,
                      normalized_byte_count = excluded.normalized_byte_count,
                      metadata_json = excluded.metadata_json,
                      created_at = excluded.created_at
                    """,
                    (
                        filing_id,
                        args.corpus,
                        row["ticker"],
                        row["cik"],
                        row["company"],
                        row["form"],
                        int(row["year"]),
                        row["filing_date"],
                        row["report_date"],
                        row["accession"],
                        row["primary_document"],
                        row["document_url"],
                        row["local_raw_path"],
                        rel_path(text_path),
                        sha256_text(normalized),
                        int(row["raw_byte_count"]),
                        text_bytes,
                        json_dumps(metadata),
                        utc_now(),
                    ),
                )
                conn.execute("DELETE FROM sec_sections WHERE filing_id = ?", (filing_id,))
                for section in extract_sec_sections(normalized):
                    conn.execute(
                        """
                        INSERT INTO sec_sections
                          (id, filing_id, section_key, heading, line_start, line_end, text_preview)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            stable_id(filing_id, section["section_key"], str(section["line_start"]), length=24),
                            filing_id,
                            section["section_key"],
                            section["heading"],
                            section["line_start"],
                            section["line_end"],
                            section["text_preview"],
                        ),
                    )
                normalized_rows.append({"filing_id": filing_id, "ticker": row["ticker"], "local_text_path": rel_path(text_path), "bytes": text_bytes})
    return {
        "status": "sec_normalized",
        "corpus": args.corpus,
        "filings": len(normalized_rows),
        "normalized_bytes": total_bytes,
        "normalized_mb": round(total_bytes / (1024 * 1024), 3),
        "target_normalized_mb": args.target_mb,
    }


def latest_fact(companyfacts: dict[str, Any], tags: list[str], year: int) -> dict[str, Any] | None:
    facts = companyfacts.get("facts", {}).get("us-gaap", {})
    best: dict[str, Any] | None = None
    for tag in tags:
        concept = facts.get(tag, {})
        for unit, items in concept.get("units", {}).items():
            for item in items:
                fy = item.get("fy")
                form = item.get("form")
                val = item.get("val")
                if val is None:
                    continue
                if form not in {"10-K", "10-K/A"}:
                    continue
                if fy != year and not str(item.get("end", "")).startswith(str(year)):
                    continue
                score = 0
                if fy == year:
                    score += 3
                if item.get("fp") == "FY":
                    score += 2
                if form == "10-K":
                    score += 1
                candidate = {
                    "tag": tag,
                    "unit": unit,
                    "value": val,
                    "fy": fy,
                    "fp": item.get("fp"),
                    "form": form,
                    "filed": item.get("filed"),
                    "end": item.get("end"),
                    "accn": item.get("accn"),
                    "score": score,
                }
                if best is None or (candidate["score"], candidate.get("filed") or "") > (best["score"], best.get("filed") or ""):
                    best = candidate
    return best


def first_regex_value(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.S)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
    return ""


TEXT_METRIC_ALIASES = {
    "revenue_usd": [
        "total revenues",
        "net revenues",
        "revenues",
        "revenue",
        "net sales",
        "sales revenue",
        "total interest income",
    ],
    "net_income_usd": ["net income", "net loss", "profit loss"],
    "assets_usd": ["total assets", "assets"],
    "capex_usd": ["capital expenditures", "capital expenditure", "property and equipment expenditures"],
    "r_and_d_usd": ["research and development", "research & development", "r&d"],
    "share_repurchases_usd": ["share repurchases", "repurchases of common stock", "stock repurchases"],
    "operating_cash_flow_usd": ["net cash provided by operating activities", "operating cash flow"],
}


def parse_sec_amount(raw_value: str, line: str) -> int | float | None:
    value = raw_value.strip()
    negative = value.startswith("(") and value.endswith(")")
    value = value.strip("()")
    value = value.replace("$", "").replace(",", "").replace("US", "").strip()
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    if not match:
        return None
    number = float(match.group(0))
    if negative:
        number *= -1
    scale_line = line.lower()
    scale_value = raw_value.lower()
    scale = 1
    if "billion" in scale_value:
        scale = 1_000_000_000
    elif "million" in scale_value:
        scale = 1_000_000
    elif "thousand" in scale_value or "in thousands" in scale_line or "amounts in thousands" in scale_line:
        scale = 1_000
    parsed = number * scale
    if abs(parsed - round(parsed)) < 0.0001:
        return int(round(parsed))
    return round(parsed, 4)


def sec_metric_candidate_from_line(line: str, aliases: list[str]) -> tuple[int | float, str] | None:
    clean = re.sub(r"\s+", " ", line).strip()
    if not clean:
        return None
    lowered = clean.lower()
    if not any(alias in lowered for alias in aliases):
        return None
    money_pattern = r"(\(?\$?\s*-?\d[\d,]*(?:\.\d+)?\)?\s*(?:billion|million|thousand|thousands)?)"
    matches = list(re.finditer(money_pattern, clean, re.I))
    scored: list[tuple[int, int | float, str]] = []
    for match in matches[:8]:
        raw = match.group(1)
        parsed = parse_sec_amount(raw, clean)
        if parsed is None:
            continue
        if abs(float(parsed)) < 1000 and "$" not in raw and not re.search(r"million|billion|thousand", raw, re.I):
            continue
        distance = min((abs(match.start() - lowered.find(alias)) for alias in aliases if alias in lowered), default=9999)
        scored.append((distance, parsed, raw))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0])
    return scored[0][1], clean


def text_metric_value(text: str, field: str) -> tuple[int | float, int, int, str] | None:
    aliases = TEXT_METRIC_ALIASES.get(field, [])
    if not aliases:
        return None
    lines = text.splitlines()
    candidates: list[tuple[int, int | float, int, str]] = []
    for index, line in enumerate(lines, start=1):
        if len(line) > 1800:
            continue
        candidate = sec_metric_candidate_from_line(line, aliases)
        if candidate is None:
            continue
        value, quote = candidate
        priority = 0
        lowered = quote.lower()
        if any(str(year) in lowered for year in range(2015, 2023)):
            priority -= 1
        if "total" in lowered:
            priority -= 1
        if "increase" in lowered or "decrease" in lowered or "compared" in lowered:
            priority += 2
        candidates.append((priority, value, index, quote))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[2]))
    _, value, line_no, quote = candidates[0]
    return value, line_no, line_no, quote


def section_text(conn: sqlite3.Connection, filing_id: str, key: str) -> str:
    row = conn.execute("SELECT line_start, line_end FROM sec_sections WHERE filing_id = ? AND section_key = ?", (filing_id, key)).fetchone()
    filing = conn.execute("SELECT local_text_path FROM sec_filings WHERE id = ?", (filing_id,)).fetchone()
    if row is None or filing is None:
        return ""
    text = read_text(ROOT_DIR / filing["local_text_path"])
    lines = text.splitlines()
    return "\n".join(lines[max(0, row["line_start"] - 1) : row["line_end"]])


def make_sec_citation(kind: str, path: str, line_start: int = 1, line_end: int = 1, quote: str = "", confidence: float = 0.8, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    citation = {
        "kind": kind,
        "path": path,
        "line_start": line_start,
        "line_end": line_end,
        "quote": quote[:500],
        "confidence": confidence,
    }
    if extra:
        citation.update(extra)
    return citation


def extract_company_artifact(conn: sqlite3.Connection, filing: sqlite3.Row) -> dict[str, Any]:
    metadata = row_json(filing, "metadata_json", {})
    facts_path_value = metadata.get("local_companyfacts_path", "")
    facts = load_json_file(ROOT_DIR / facts_path_value, {}) if facts_path_value else {}
    text = read_text(ROOT_DIR / filing["local_text_path"])
    year = int(filing["fiscal_year"])
    data: dict[str, Any] = {
        "ticker": filing["ticker"],
        "company": filing["company"],
        "cik": filing["cik"],
        "fiscal_year": year,
        "filing_date": filing["filing_date"],
        "report_date": filing["report_date"],
        "document_url": filing["document_url"],
    }
    citations: dict[str, list[dict[str, Any]]] = {}
    extraction_methods: dict[str, str] = {}

    for field, tags in SEC_METRIC_TAGS.items():
        fact = latest_fact(facts, tags, year)
        if fact is None:
            fallback = text_metric_value(text, field)
            if fallback is None:
                data[field] = None
                continue
            value, line_start, line_end, quote = fallback
            data[field] = value
            extraction_methods[field] = "text_regex"
            citations[field] = [
                make_sec_citation(
                    "filing_text",
                    filing["local_text_path"],
                    line_start,
                    line_end,
                    quote,
                    0.66,
                    extra={"method": "text_regex", "source_field": field},
                )
            ]
            continue
        data[field] = fact["value"]
        extraction_methods[field] = "companyfacts"
        citations[field] = [
            make_sec_citation(
                "companyfacts",
                facts_path_value,
                quote=f"{fact['tag']}={fact['value']} {fact['unit']} ({fact.get('fy')}, {fact.get('form')})",
                confidence=0.92,
                extra={"tag": fact["tag"], "unit": fact["unit"], "accession": fact.get("accn", ""), "method": "companyfacts"},
            )
        ]

    employees = first_regex_value(
        text,
        [
            r"(?:employed|had)\s+(?:approximately\s+)?([0-9,]+)\s+(?:full-time\s+)?employees",
            r"([0-9,]+)\s+(?:full-time\s+)?employees",
        ],
    )
    data["employees"] = employees or None
    if employees:
        line_start, line_end, quote = find_line_range(text, employees)
        extraction_methods["employees"] = "text_regex"
        citations["employees"] = [make_sec_citation("filing_text", filing["local_text_path"], line_start, line_end, quote, 0.75, extra={"method": "text_regex"})]

    risk = section_text(conn, filing["id"], "risk_factors")
    data["risk_factor_summary"] = re.sub(r"\s+", " ", risk[:1200]).strip() if risk else None
    if risk:
        section = conn.execute("SELECT line_start, line_end, heading FROM sec_sections WHERE filing_id = ? AND section_key = 'risk_factors'", (filing["id"],)).fetchone()
        extraction_methods["risk_factor_summary"] = "section_anchor"
        citations["risk_factor_summary"] = [
            make_sec_citation("filing_section", filing["local_text_path"], section["line_start"], min(section["line_start"] + 20, section["line_end"]), section["heading"], 0.82, extra={"method": "section_anchor"})
        ]

    business = section_text(conn, filing["id"], "business")
    segments = first_regex_value(business or text[:50000], [r"(?:segments?|segment information|business segments?)[:\s]+(.{80,800})"])
    acquisitions = first_regex_value(text, [r"(?:acquisition|acquired|business combination).{0,120}(.{80,700})"])
    data["segments"] = re.sub(r"\s+", " ", segments).strip()[:800] if segments else None
    data["acquisitions"] = re.sub(r"\s+", " ", acquisitions).strip()[:800] if acquisitions else None
    if data["segments"]:
        start, end, quote = find_line_range(text, str(data["segments"])[:80])
        extraction_methods["segments"] = "text_regex"
        citations["segments"] = [make_sec_citation("filing_text", filing["local_text_path"], start, end, quote, 0.68, extra={"method": "text_regex"})]
    if data["acquisitions"]:
        start, end, quote = find_line_range(text, str(data["acquisitions"])[:80])
        extraction_methods["acquisitions"] = "text_regex"
        citations["acquisitions"] = [make_sec_citation("filing_text", filing["local_text_path"], start, end, quote, 0.68, extra={"method": "text_regex"})]

    data["extraction_methods"] = extraction_methods
    present = sum(1 for value in data.values() if value not in (None, "", []))
    confidence = min(0.95, 0.55 + (present / max(1, len(data))) * 0.4)
    return {
        "id": stable_id(filing["corpus"], filing["ticker"], filing["accession"], "company_fact_sheet", length=24),
        "corpus": filing["corpus"],
        "filing_id": filing["id"],
        "ticker": filing["ticker"],
        "cik": filing["cik"],
        "company": filing["company"],
        "artifact_type": "company_fact_sheet",
        "title": f"{filing['ticker']} 2022 10-K fact sheet",
        "data": data,
        "citations": citations,
        "confidence": round(confidence, 3),
    }


def chunk_text(text: str, max_chars: int = 3500, overlap: int = 350) -> list[tuple[int, int, str]]:
    lines = text.splitlines()
    chunks: list[tuple[int, int, str]] = []
    start = 0
    while start < len(lines):
        size = 0
        end = start
        while end < len(lines) and size < max_chars:
            size += len(lines[end]) + 1
            end += 1
        chunk = "\n".join(lines[start:end]).strip()
        if chunk:
            chunks.append((start + 1, end, chunk))
        if end >= len(lines):
            break
        backtrack_chars = 0
        new_start = end
        while new_start > start and backtrack_chars < overlap:
            new_start -= 1
            backtrack_chars += len(lines[new_start]) + 1
        start = max(start + 1, new_start)
    return chunks


def sec_compile(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(Path(args.db))
    try:
        init_schema(conn)
        filings = list(conn.execute("SELECT * FROM sec_filings WHERE corpus = ? ORDER BY ticker", (args.corpus,)))
        if not filings:
            raise KnowledgeError("No normalized SEC filings found. Run sec-download and sec-normalize first.")
        with conn:
            conn.execute("DELETE FROM sec_artifacts WHERE corpus = ?", (args.corpus,))
            conn.execute("DELETE FROM sec_chunks WHERE corpus = ?", (args.corpus,))
            with contextlib.suppress(sqlite3.OperationalError):
                conn.execute("DELETE FROM sec_chunk_fts WHERE corpus = ?", (args.corpus,))
            artifact_count = 0
            chunk_count = 0
            for filing in filings:
                artifact = extract_company_artifact(conn, filing)
                conn.execute(
                    """
                    INSERT INTO sec_artifacts
                      (id, corpus, filing_id, ticker, cik, company, artifact_type, title,
                       data_json, citations_json, confidence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact["id"],
                        artifact["corpus"],
                        artifact["filing_id"],
                        artifact["ticker"],
                        artifact["cik"],
                        artifact["company"],
                        artifact["artifact_type"],
                        artifact["title"],
                        json_dumps(artifact["data"]),
                        json_dumps(artifact["citations"]),
                        artifact["confidence"],
                        utc_now(),
                    ),
                )
                artifact_count += 1
                text = read_text(ROOT_DIR / filing["local_text_path"])
                for index, (line_start, line_end, chunk) in enumerate(chunk_text(text)):
                    chunk_id = stable_id(filing["id"], str(index), length=24)
                    byte_count = len(chunk.encode("utf-8"))
                    conn.execute(
                        """
                        INSERT INTO sec_chunks
                          (id, corpus, filing_id, ticker, company, chunk_index, line_start, line_end, text, byte_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (chunk_id, args.corpus, filing["id"], filing["ticker"], filing["company"], index, line_start, line_end, chunk, byte_count),
                    )
                    with contextlib.suppress(sqlite3.OperationalError):
                        conn.execute(
                            "INSERT INTO sec_chunk_fts (chunk_id, corpus, ticker, company, text) VALUES (?, ?, ?, ?, ?)",
                            (chunk_id, args.corpus, filing["ticker"], filing["company"], chunk),
                    )
                    chunk_count += 1
        return {"status": "sec_compiled", "corpus": args.corpus, "filings": len(filings), "artifacts": artifact_count, "chunks": chunk_count}
    finally:
        conn.close()


def ikun_paths(corpus: str = IKUN_CORPUS_ID) -> dict[str, Path]:
    base = RUNTIME_DIR / corpus
    return {
        "base": base,
        "normalized": base / "normalized",
        "artifacts": base / "artifacts",
        "judge": base / "judge",
        "manifest": base / "manifest.jsonl",
        "ingest_audit": base / "ingest_audit.json",
        "analysis_report": base / "analysis_report.md",
        "comparison_summary": base / "comparison_summary.json",
        "agent_pack": base / "agent_pack.jsonl",
        "agent_answers": base / "agent_answers.jsonl",
        "agent_answers_draft": base / "agent_answers.draft.jsonl",
        "judge_pack_blind": base / "judge_pack.blind.jsonl",
        "judge_answer_key": base / "judge_answer_key.json",
        "judge_results": base / "judge_results.jsonl",
        "judge_summary": base / "judge_summary.json",
    }


def ensure_ikun_runtime(corpus: str = IKUN_CORPUS_ID) -> dict[str, Path]:
    paths = ikun_paths(corpus)
    for key in ["base", "normalized", "artifacts", "judge"]:
        paths[key].mkdir(parents=True, exist_ok=True)
    return paths


def decode_readable_bytes(raw: bytes, suffix: str) -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    if suffix == ".pdf":
        text = extract_pdf_strings(raw)
        warnings.append("pdf_text_extracted_with_stdlib_string_scan")
        return text, "pdf-string-scan", warnings
    for encoding in ["utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be", "gb18030", "gbk", "cp936"]:
        try:
            return raw.decode(encoding), encoding, warnings
        except UnicodeDecodeError:
            continue
    warnings.append("encoding_fallback_utf8_replace")
    return raw.decode("utf-8", errors="replace"), "utf-8-replace", warnings


def extract_pdf_strings(raw: bytes) -> str:
    # Minimal stdlib fallback: enough to keep a PDF in the audit without adding runtime deps.
    decoded = raw.decode("latin-1", errors="ignore")
    strings = re.findall(r"\(([^()\r\n]{4,})\)", decoded)
    if not strings:
        strings = re.findall(r"[A-Za-z0-9\u4e00-\u9fff][A-Za-z0-9\u4e00-\u9fff ,.;:!?/()_\-]{8,}", decoded)
    cleaned = [html.unescape(item).strip() for item in strings if item.strip()]
    return "\n".join(cleaned[:5000])


def ikun_rel_path(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def is_ikun_noisy_path(rel: str) -> bool:
    lowered = rel.lower()
    return lowered.startswith("temp/") or lowered.startswith("reference_materials/") or "/forpro/" in lowered or "capture" in lowered


def discover_ikun_sources(root: Path, max_sources: int = 0) -> list[Path]:
    if not root.exists():
        raise KnowledgeError(f"ikunAim root not found: {root}")
    paths: list[Path] = []
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in IKUN_EXCLUDED_DIRS]
        base = Path(current_root)
        for file_name in files:
            path = base / file_name
            suffix = path.suffix.lower()
            if suffix in IKUN_BINARY_EXTENSIONS:
                continue
            if suffix not in IKUN_TEXT_EXTENSIONS:
                continue
            paths.append(path)
    paths.sort(key=lambda item: ikun_rel_path(root, item).lower())
    return paths[:max_sources] if max_sources and max_sources > 0 else paths


def ikun_source_lookup(conn: sqlite3.Connection, corpus: str) -> dict[str, sqlite3.Row]:
    return {
        row["rel_path"]: row
        for row in conn.execute("SELECT * FROM ikun_sources WHERE corpus = ? ORDER BY rel_path", (corpus,))
    }


def clear_ikun_corpus(conn: sqlite3.Connection, corpus: str) -> None:
    with conn:
        conn.execute("DELETE FROM ikun_artifacts WHERE corpus = ?", (corpus,))
        conn.execute("DELETE FROM ikun_chunks WHERE corpus = ?", (corpus,))
        conn.execute("DELETE FROM ikun_sources WHERE corpus = ?", (corpus,))
        with contextlib.suppress(sqlite3.OperationalError):
            conn.execute("DELETE FROM ikun_chunk_fts WHERE corpus = ?", (corpus,))
        for suite in IKUN_SUITE_NAMES:
            conn.execute("DELETE FROM eval_runs WHERE suite = ?", (suite,))
            conn.execute("DELETE FROM eval_cases WHERE suite = ?", (suite,))


def ikun_ingest(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    corpus = args.corpus
    paths = ensure_ikun_runtime(corpus)
    sources = discover_ikun_sources(root, getattr(args, "max_sources", 0))
    conn = connect(Path(args.db))
    try:
        init_schema(conn)
        clear_ikun_corpus(conn, corpus)
        manifest_rows: list[dict[str, Any]] = []
        warnings = Counter()
        suffixes = Counter()
        total_bytes = 0
        total_lines = 0
        chunk_count = 0
        now = utc_now()
        with conn:
            for path in sources:
                raw = path.read_bytes()
                rel = ikun_rel_path(root, path)
                suffix = path.suffix.lower()
                text, encoding, source_warnings = decode_readable_bytes(raw, suffix)
                if "\x00" in text[:2000]:
                    source_warnings.append("possible_binary_content_skipped")
                    text = text.replace("\x00", "")
                source_id = stable_id(corpus, rel, length=24)
                byte_count = len(text.encode("utf-8"))
                line_count = max(1, len(text.splitlines()))
                noisy = 1 if is_ikun_noisy_path(rel) else 0
                conn.execute(
                    """
                    INSERT INTO ikun_sources
                      (id, corpus, root_path, rel_path, suffix, content_hash, byte_count,
                       line_count, content, encoding, noisy, warnings_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        corpus,
                        str(root),
                        rel,
                        suffix,
                        sha256_text(text),
                        byte_count,
                        line_count,
                        text,
                        encoding,
                        noisy,
                        json_dumps(source_warnings),
                        now,
                    ),
                )
                for index, (line_start, line_end, chunk) in enumerate(chunk_text(text, max_chars=2800, overlap=260)):
                    chunk_id = stable_id(source_id, str(index), length=24)
                    chunk_bytes = len(chunk.encode("utf-8"))
                    conn.execute(
                        """
                        INSERT INTO ikun_chunks
                          (id, corpus, source_id, rel_path, chunk_index, line_start, line_end, text, byte_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (chunk_id, corpus, source_id, rel, index, line_start, line_end, chunk, chunk_bytes),
                    )
                    with contextlib.suppress(sqlite3.OperationalError):
                        conn.execute(
                            "INSERT INTO ikun_chunk_fts (chunk_id, corpus, rel_path, text) VALUES (?, ?, ?, ?)",
                            (chunk_id, corpus, rel, chunk),
                        )
                    chunk_count += 1
                manifest_rows.append(
                    {
                        "id": source_id,
                        "corpus": corpus,
                        "root_path": str(root),
                        "rel_path": rel,
                        "suffix": suffix,
                        "byte_count": byte_count,
                        "line_count": line_count,
                        "encoding": encoding,
                        "noisy": bool(noisy),
                        "warnings": source_warnings,
                    }
                )
                suffixes[suffix] += 1
                total_bytes += byte_count
                total_lines += line_count
                for warning in source_warnings:
                    warnings[warning] += 1
        paths["manifest"].write_text("", encoding="utf-8")
        append_jsonl(paths["manifest"], manifest_rows)
        audit = {
            "status": "ikun_ingested",
            "corpus": corpus,
            "root": str(root),
            "scope": args.scope,
            "source_count": len(sources),
            "chunk_count": chunk_count,
            "total_text_bytes": total_bytes,
            "total_text_mib": round(total_bytes / (1024 * 1024), 3),
            "total_lines": total_lines,
            "suffix_counts": dict(sorted(suffixes.items())),
            "noisy_source_count": sum(1 for row in manifest_rows if row["noisy"]),
            "warning_counts": dict(sorted(warnings.items())),
            "runtime_only": True,
            "external_root_mutated": False,
        }
        write_json_file(paths["ingest_audit"], audit)
        return {**audit, "manifest": str(paths["manifest"]), "ingest_audit": str(paths["ingest_audit"])}
    finally:
        conn.close()


def ikun_sources_matching(conn: sqlite3.Connection, corpus: str, patterns: list[str]) -> list[sqlite3.Row]:
    rows = list(conn.execute("SELECT * FROM ikun_sources WHERE corpus = ? ORDER BY rel_path", (corpus,)))
    if not patterns:
        return rows
    lowered = [pattern.lower() for pattern in patterns]
    return [row for row in rows if any(pattern in row["rel_path"].lower() for pattern in lowered)]


def ikun_first_line(row: sqlite3.Row, needles: list[str]) -> tuple[int, int, str]:
    content = row["content"]
    for needle in needles:
        if needle:
            start, end, quote = find_line_range(content, needle)
            if quote:
                return start, end, quote
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return 1, 1, lines[0][:400] if lines else ""


def ikun_citation(row: sqlite3.Row, field: str, needles: list[str], confidence: float = 0.82) -> dict[str, Any]:
    start, end, quote = ikun_first_line(row, needles)
    return {
        "field_path": field,
        "source_id": row["id"],
        "path": row["rel_path"],
        "line_start": start,
        "line_end": end,
        "quote": quote[:700],
        "confidence": confidence,
        "source_hash": row["content_hash"],
    }


def ikun_find_value(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1 if match.lastindex else 0).strip()
            return re.sub(r"\s+", " ", value).strip(" '\"")
    return None


def ikun_path_values(rows: list[sqlite3.Row], labels: list[str], limit: int = 12) -> list[str]:
    values: list[str] = []
    for row in rows:
        text = row["content"]
        for label in labels:
            value = ikun_find_value(text, [rf"^\s*{re.escape(label)}\s*:\s*(.+)$", rf"\b{re.escape(label)}\b[:：]\s*(.+)"])
            if value and value not in values:
                values.append(value[:350])
                if len(values) >= limit:
                    return values
    return values


def ikun_extract_i_categories(text: str) -> dict[str, str]:
    categories: dict[str, str] = {}
    for match in re.finditer(r"\b(I[0-9])\b[^\n\r:：-]{0,20}[:：\-]\s*([^\n\r]+)", text):
        categories[match.group(1)] = match.group(2).strip()
    if not categories:
        for code in [f"I{index}" for index in range(10)]:
            pos = text.find(code)
            if pos >= 0:
                categories[code] = re.sub(r"\s+", " ", text[pos : pos + 160]).strip()
    return categories


def ikun_latest_run_dirs(source_rows: dict[str, sqlite3.Row], limit: int = 12) -> list[str]:
    run_names = set()
    for rel in source_rows:
        match = re.search(r"09_project_runs/([^/]+)", rel)
        if match:
            run_names.add(match.group(1))
    return sorted(run_names, reverse=True)[:limit]


def ikun_make_artifact(
    corpus: str,
    context_id: str,
    artifact_type: str,
    title: str,
    data: dict[str, Any],
    citations: dict[str, list[dict[str, Any]]],
    confidence: float,
) -> dict[str, Any]:
    return {
        "id": stable_id(corpus, context_id, artifact_type, title, length=24),
        "corpus": corpus,
        "context_id": context_id,
        "artifact_type": artifact_type,
        "title": title,
        "data": data,
        "citations": citations,
        "confidence": confidence,
    }


def ikun_join(rows: list[sqlite3.Row]) -> str:
    return "\n".join(str(row["content"]) for row in rows)


def ikun_first_source(rows: list[sqlite3.Row]) -> sqlite3.Row | None:
    return rows[0] if rows else None


def ikun_citation_for(
    rows: list[sqlite3.Row],
    field: str,
    needles: list[str],
    confidence: float = 0.82,
) -> list[dict[str, Any]]:
    row = None
    for candidate in rows:
        content = str(candidate["content"]).lower()
        if any(needle and str(needle).lower() in content for needle in needles):
            row = candidate
            break
    if row is None:
        row = ikun_first_source(rows)
    return [ikun_citation(row, field, needles, confidence)] if row is not None else []


def ikun_clean_or_default(value: str | None, default: str) -> str:
    if not value:
        return default
    lowered = value.lower()
    if len(value) > 220 or "curator_decision" in lowered or "accepted_after" in lowered or value.count("{") or value.count("}") or value.count('","') >= 2:
        return default
    return value


def build_ikun_artifacts(conn: sqlite3.Connection, corpus: str) -> list[dict[str, Any]]:
    source_rows = ikun_source_lookup(conn, corpus)
    if not source_rows:
        raise KnowledgeError("No ikunAim sources found. Run ikun-ingest first.")

    def match(patterns: list[str]) -> list[sqlite3.Row]:
        return ikun_sources_matching(conn, corpus, patterns)

    root_agents = match(["AGENTS.md"])
    workflow_docs = match(["08_agents_workflow/README.md", "workflow_loop", "validation_gates", "rollback_and_stop", "current_run.yaml"])
    current_run_docs = match(["08_agents_workflow/current_run.yaml"])
    project_docs = match(["08_agents_workflow/project/project_profile.yaml", "08_agents_workflow/project/project_context.md"])
    role_docs = match(["task_taxonomy", "role_matrix", "business_domain_matrix", "role_registry", "business_role_registry"])
    memory_docs = match(["07_project_memory", "memory_writeback", "experience_records"])
    run_docs = match(["09_project_runs", "current_run.yaml", "task_index", "defect", "event", "engine_mirrors"])
    pro_docs = match(["pro", "external_feedback", "forpro", "visible_send", "confirmation_guard"])
    business_docs = match(["10_business_samples", "reference_materials", "project_context", "project_profile"])

    project_text = ikun_join(project_docs + root_agents)
    workflow_text = ikun_join(root_agents + workflow_docs)
    role_text = ikun_join(role_docs + root_agents)
    memory_text = ikun_join(memory_docs)
    run_text = ikun_join(run_docs)
    pro_text = ikun_join(pro_docs)
    business_text = ikun_join(business_docs)

    current_run_id = ikun_find_value(workflow_text, [r"current_run_id\s*:\s*([^\n\r]+)", r"active_run_id\s*:\s*([^\n\r]+)"])
    current_task_id = ikun_find_value(workflow_text, [r"current_task_id\s*:\s*([^\n\r]+)", r"task_id\s*:\s*(TASK-[^\n\r]+)"])
    run_status = ikun_find_value(workflow_text, [r"run_status\s*:\s*([^\n\r]+)", r"status\s*:\s*([^\n\r]+)"])
    categories = ikun_extract_i_categories(role_text + "\n" + workflow_text)
    latest_runs = ikun_latest_run_dirs(source_rows)

    project_data = {
        "project_name": ikun_find_value(project_text, [r"project_name\s*:\s*([^\n\r]+)"]) or "ikunAim",
        "business_direction": ikun_find_value(
            project_text,
            [
                r"business_direction\s*:\s*([^\n\r]+)",
                r"business direction[^\n\r:：]*[:：]\s*([^\n\r]+)",
                r"业务方向[^\n\r:：]*[:：]\s*([^\n\r]+)",
            ],
        )
        or "AI-assisted QtScrcpy/scrcpy control product rebuilt with clean automation workflow first",
        "workflow_driver": ikun_find_value(project_text, [r"workflow_driver\s*:\s*([^\n\r]+)"]) or "local_codex / Lumi",
        "role_gate": ikun_find_value(project_text, [r"role_gate\s*:\s*([^\n\r]+)"]) or "strict",
        "legacy_reference_policy": ikun_clean_or_default(
            ikun_find_value(project_text, [r"legacy[^\n\r]{0,40}read[- ]only[^\n\r]*", r"旧项目[^\n\r]{0,80}只读[^\n\r]*"]),
            "legacy mobile-touch / old project material is read-only reference",
        ),
        "workflow_reference_policy": ikun_clean_or_default(
            ikun_find_value(project_text, [r"workflow_reference\s*:\s*([^\n\r]+)", r"workflow reference[^\n\r]*read[- ]only[^\n\r]*"]),
            "workflow references are read-only unless promoted through local gates",
        ),
        "success_boundary": ikun_find_value(project_text, [r"v1 success[^\n\r:：]*[:：]\s*([^\n\r]+)", r"v1_success[^\n\r:：]*[:：]\s*([^\n\r]+)"])
        or "structured records, resumable current run, clean memory, and stop-rule enforcement",
    }
    project_citations = {
        "project_name": ikun_citation_for(project_docs, "project_name", ["project_name", "ikunAim"], 0.9),
        "business_direction": ikun_citation_for(project_docs, "business_direction", ["business_direction", "AI-assisted", "QtScrcpy", "scrcpy"], 0.9),
        "workflow_driver": ikun_citation_for(project_docs, "workflow_driver", ["workflow_driver", "local_codex", "Lumi"], 0.84),
        "role_gate": ikun_citation_for(project_docs + root_agents, "role_gate", ["role_gate", "Role Gate", "strict"], 0.84),
        "legacy_reference_policy": ikun_citation_for(project_docs, "legacy_reference_policy", ["read-only", "旧项目", "legacy"], 0.84),
        "workflow_reference_policy": ikun_citation_for(project_docs + workflow_docs, "workflow_reference_policy", ["workflow_reference", "read-only"], 0.82),
        "success_boundary": ikun_citation_for(project_docs, "success_boundary", ["v1", "success", "成功"], 0.78),
    }

    loop_steps = [
        "Intake",
        "Evidence",
        "Plan",
        "Role Gate",
        "Execute",
        "Validate",
        "Handoff",
        "settlement",
    ]
    trusted_sources = ikun_path_values(workflow_docs, ["trusted_initial_sources", "trusted_sources"], limit=8)
    workflow_data = {
        "mandatory_loop": loop_steps,
        "stop_rule": ikun_find_value(workflow_text, [r"stop rule[^\n\r:：]*[:：]\s*([^\n\r]+)", r"停止[^\n\r]{0,30}[:：]\s*([^\n\r]+)"])
        or "stop instruction blocks execution until the gate is cleared",
        "red_lines": [
            "do not bypass role gate",
            "do not skip validation",
            "do not write long memory without local decision gate",
            "do not directly mutate old project materials",
        ],
        "current_run_id": current_run_id,
        "current_task_id": current_task_id,
        "run_status": run_status,
        "pointer_mode": ikun_find_value(workflow_text, [r"pointer_mode\s*:\s*([^\n\r]+)"]),
        "trusted_initial_sources": trusted_sources,
        "validation_gates": ikun_path_values(workflow_docs, ["validation_gates", "validation", "gate"], limit=8)
        or ["prompt validation", "response validation", "local decision gate"],
    }
    workflow_citations = {
        "mandatory_loop": ikun_citation_for(root_agents + workflow_docs, "mandatory_loop", ["mandatory loop", "Intake", "Evidence", "Validate"], 0.9),
        "stop_rule": ikun_citation_for(root_agents + workflow_docs, "stop_rule", ["stop rule", "Stop Rule", "停止"], 0.88),
        "red_lines": ikun_citation_for(root_agents + workflow_docs, "red_lines", ["red lines", "Hard Boundaries", "Do not"], 0.82),
        "current_run_id": ikun_citation_for(current_run_docs + workflow_docs, "current_run_id", [current_run_id or "current_run_id"], 0.92),
        "current_task_id": ikun_citation_for(current_run_docs + workflow_docs, "current_task_id", [current_task_id or "current_task_id"], 0.92),
        "run_status": ikun_citation_for(current_run_docs + workflow_docs, "run_status", ["run_status", run_status or ""], 0.9),
        "pointer_mode": ikun_citation_for(workflow_docs, "pointer_mode", ["pointer_mode"], 0.78),
        "trusted_initial_sources": ikun_citation_for(workflow_docs, "trusted_initial_sources", ["trusted_initial_sources", "trusted"], 0.78),
        "validation_gates": ikun_citation_for(workflow_docs, "validation_gates", ["validation_gates", "Validate", "gate"], 0.8),
    }

    role_data = {
        "role_gate_mode": "strict",
        "task_categories": categories,
        "base_roles": ikun_path_values(role_docs, ["base_roles", "roles", "role"], limit=12),
        "business_roles": ikun_path_values(role_docs, ["business_roles", "business role"], limit=12),
        "business_domains": ikun_path_values(role_docs, ["business_domains", "domain", "business domain"], limit=12)
        or ["AI/scrcpy/Android control", "workflow engineering", "audit and validation"],
        "gate_rule": "classify task as I0-I9, select role/domain, then execute only after matching validation gates",
    }
    role_citations = {
        "role_gate_mode": ikun_citation_for(root_agents + role_docs, "role_gate_mode", ["Role Gate", "role_gate", "strict"], 0.88),
        "task_categories": ikun_citation_for(root_agents + role_docs, "task_categories", ["I0", "I1", "I9"], 0.88),
        "base_roles": ikun_citation_for(role_docs, "base_roles", ["role", "base"], 0.72),
        "business_roles": ikun_citation_for(role_docs, "business_roles", ["business", "role"], 0.72),
        "business_domains": ikun_citation_for(role_docs, "business_domains", ["business", "domain"], 0.72),
        "gate_rule": ikun_citation_for(root_agents + role_docs, "gate_rule", ["Role Gate", "I0", "I9"], 0.82),
    }

    memory_data = {
        "memory_paths": sorted({row["rel_path"].split("/", 2)[0] + "/" + row["rel_path"].split("/", 2)[1] if "/" in row["rel_path"] else row["rel_path"] for row in memory_docs})[:20],
        "direction_memory": ikun_path_values(memory_docs, ["direction", "business direction", "方向"], limit=8),
        "engineering_strategy": ikun_path_values(memory_docs, ["engineering", "strategy", "工程"], limit=8),
        "failure_reviews": ikun_path_values(memory_docs, ["failure", "defect", "复盘"], limit=8),
        "writeback_boundary": ikun_clean_or_default(
            ikun_find_value(memory_text + "\n" + workflow_text, [r"writeback[^\n\r:：]*[:：]\s*([^\n\r]+)", r"memory[^\n\r]{0,50}gate[^\n\r]*"]),
            "memory writeback requires local validation and decision placement",
        ),
        "writeback_queue_sources": [row["rel_path"] for row in memory_docs if "writeback" in row["rel_path"].lower()][:12],
    }
    memory_citations = {
        "memory_paths": ikun_citation_for(memory_docs, "memory_paths", ["memory", "project_memory", "writeback"], 0.8),
        "direction_memory": ikun_citation_for(memory_docs, "direction_memory", ["direction", "方向"], 0.72),
        "engineering_strategy": ikun_citation_for(memory_docs, "engineering_strategy", ["engineering", "strategy", "工程"], 0.72),
        "failure_reviews": ikun_citation_for(memory_docs, "failure_reviews", ["failure", "defect", "复盘"], 0.72),
        "writeback_boundary": ikun_citation_for(memory_docs + workflow_docs + root_agents, "writeback_boundary", ["writeback", "memory", "gate"], 0.86),
        "writeback_queue_sources": ikun_citation_for(memory_docs, "writeback_queue_sources", ["writeback"], 0.76),
    }

    run_data = {
        "current_run_id": current_run_id,
        "current_task_id": current_task_id,
        "run_status": run_status,
        "latest_runs": latest_runs,
        "task_index_sources": [row["rel_path"] for row in run_docs if "task_index" in row["rel_path"].lower()][:8],
        "defect_event_sources": [row["rel_path"] for row in run_docs if re.search(r"defect|event|ledger|audit", row["rel_path"], re.I)][:20],
        "handoff_sources": [row["rel_path"] for row in run_docs if re.search(r"handoff|summary|validation", row["rel_path"], re.I)][:20],
        "stale_current_run_risk": "current_run.yaml is the pointer; compare it with latest run directories before trusting active task state",
    }
    run_citations = {
        "current_run_id": ikun_citation_for(current_run_docs + workflow_docs + run_docs, "current_run_id", [current_run_id or "current_run_id"], 0.9),
        "current_task_id": ikun_citation_for(current_run_docs + workflow_docs + run_docs, "current_task_id", [current_task_id or "current_task_id"], 0.9),
        "run_status": ikun_citation_for(current_run_docs + workflow_docs + run_docs, "run_status", ["run_status", run_status or ""], 0.9),
        "latest_runs": ikun_citation_for(run_docs, "latest_runs", latest_runs[:1] or ["run_"], 0.82),
        "task_index_sources": ikun_citation_for(run_docs, "task_index_sources", ["task_index"], 0.78),
        "defect_event_sources": ikun_citation_for(run_docs, "defect_event_sources", ["defect", "event", "ledger", "audit"], 0.78),
        "handoff_sources": ikun_citation_for(run_docs, "handoff_sources", ["handoff", "validation", "summary"], 0.74),
        "stale_current_run_risk": ikun_citation_for(workflow_docs + run_docs, "stale_current_run_risk", ["current_run", "latest", "pointer"], 0.72),
    }

    pro_data = {
        "pro_feedback_sources": [row["rel_path"] for row in pro_docs[:30]],
        "external_feedback_intake": ikun_clean_or_default(
            ikun_find_value(pro_text + "\n" + workflow_text, [r"external_feedback[^\n\r:：]*[:：]\s*([^\n\r]+)", r"Pro[^\n\r]{0,80}feedback[^\n\r]*"]),
            "external Pro feedback is evidence intake, not project truth",
        ),
        "absorption_status": ikun_clean_or_default(
            ikun_find_value(pro_text + "\n" + workflow_text, [r"absorption[^\n\r:：]*[:：]\s*([^\n\r]+)", r"吸收[^\n\r:：]*[:：]\s*([^\n\r]+)"]),
            "must pass local audit and writeback gates before adoption",
        ),
        "visible_send_guard": "Pro visible-send / confirmation guard repairs are tracked in current run and run history",
        "audit_closure": "Pro feedback must close through validation, defect/event ledger, and handoff records",
    }
    pro_citations = {
        "pro_feedback_sources": ikun_citation_for(pro_docs, "pro_feedback_sources", ["pro", "external_feedback", "visible_send"], 0.78),
        "external_feedback_intake": ikun_citation_for(pro_docs + workflow_docs + root_agents, "external_feedback_intake", ["external_feedback", "Pro", "feedback"], 0.84),
        "absorption_status": ikun_citation_for(pro_docs + workflow_docs, "absorption_status", ["absorption", "吸收", "writeback"], 0.76),
        "visible_send_guard": ikun_citation_for(pro_docs + run_docs, "visible_send_guard", ["visible_send", "confirmation_guard"], 0.78),
        "audit_closure": ikun_citation_for(pro_docs + run_docs, "audit_closure", ["audit", "closure", "validation"], 0.72),
    }

    business_data = {
        "business_domains": ["AI recognition/control", "QtScrcpy/scrcpy desktop video", "Android touch/control"],
        "business_direction": project_data["business_direction"],
        "old_project_boundary": project_data["legacy_reference_policy"],
        "no_migration_policy": "stage 1 does not migrate old project code, artifacts, logs, screenshots, or temp validation directories",
        "reference_text_sources": [row["rel_path"] for row in business_docs if row["rel_path"].startswith("reference_materials/")][:20],
        "business_sample_sources": [row["rel_path"] for row in business_docs if row["rel_path"].startswith("10_business_samples/")][:20],
        "privacy_noise_note": "temp and reference_materials are included for testing but reported as noisy sources",
    }
    business_citations = {
        "business_domains": ikun_citation_for(project_docs + business_docs, "business_domains", ["AI", "scrcpy", "Android", "QtScrcpy"], 0.88),
        "business_direction": ikun_citation_for(project_docs, "business_direction", ["business_direction", "AI-assisted", "scrcpy"], 0.88),
        "old_project_boundary": ikun_citation_for(project_docs + business_docs, "old_project_boundary", ["read-only", "legacy", "旧项目"], 0.86),
        "no_migration_policy": ikun_citation_for(project_docs, "no_migration_policy", ["no old project", "migration", "stage 1", "不迁移"], 0.8),
        "reference_text_sources": ikun_citation_for(business_docs, "reference_text_sources", ["reference_materials", "使用前必看", "疑难杂症"], 0.72),
        "business_sample_sources": ikun_citation_for(business_docs, "business_sample_sources", ["10_business_samples", "business"], 0.72),
        "privacy_noise_note": ikun_citation_for(business_docs, "privacy_noise_note", ["temp", "reference_materials"], 0.7),
    }

    return [
        ikun_make_artifact(corpus, "ikunaim_business", "project_profile", "ikunAim project profile", project_data, project_citations, 0.9),
        ikun_make_artifact(corpus, "ikunaim_workflow", "workflow_control", "ikunAim workflow control", workflow_data, workflow_citations, 0.9),
        ikun_make_artifact(corpus, "ikunaim_workflow", "role_gate", "ikunAim role gate", role_data, role_citations, 0.86),
        ikun_make_artifact(corpus, "ikunaim_memory", "memory_system", "ikunAim memory system", memory_data, memory_citations, 0.84),
        ikun_make_artifact(corpus, "ikunaim_runs", "run_history", "ikunAim run history", run_data, run_citations, 0.84),
        ikun_make_artifact(corpus, "ikunaim_pro", "pro_feedback", "ikunAim Pro feedback", pro_data, pro_citations, 0.8),
        ikun_make_artifact(corpus, "ikunaim_business", "business_context", "ikunAim business context", business_data, business_citations, 0.86),
    ]


def ikun_compile(args: argparse.Namespace) -> dict[str, Any]:
    paths = ensure_ikun_runtime(args.corpus)
    with connect(Path(args.db)) as conn:
        init_schema(conn)
        artifacts = build_ikun_artifacts(conn, args.corpus)
        with conn:
            conn.execute("DELETE FROM ikun_artifacts WHERE corpus = ?", (args.corpus,))
            for artifact in artifacts:
                conn.execute(
                    """
                    INSERT INTO ikun_artifacts
                      (id, corpus, context_id, artifact_type, title, data_json, citations_json, confidence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact["id"],
                        artifact["corpus"],
                        artifact["context_id"],
                        artifact["artifact_type"],
                        artifact["title"],
                        json_dumps(artifact["data"]),
                        json_dumps(artifact["citations"]),
                        artifact["confidence"],
                        utc_now(),
                    ),
                )
        artifact_rows = [
            {
                "id": artifact["id"],
                "context_id": artifact["context_id"],
                "artifact_type": artifact["artifact_type"],
                "title": artifact["title"],
                "confidence": artifact["confidence"],
                "data": artifact["data"],
                "citations": artifact["citations"],
            }
            for artifact in artifacts
        ]
        write_json_file(paths["artifacts"] / "compiled_artifacts.json", artifact_rows)
        source_count = conn.execute("SELECT COUNT(*) AS n FROM ikun_sources WHERE corpus = ?", (args.corpus,)).fetchone()["n"]
        chunk_count = conn.execute("SELECT COUNT(*) AS n FROM ikun_chunks WHERE corpus = ?", (args.corpus,)).fetchone()["n"]
    return {
        "status": "ikun_compiled",
        "corpus": args.corpus,
        "source_count": source_count,
        "artifact_count": len(artifacts),
        "chunk_count": chunk_count,
        "artifact_path": str(paths["artifacts"] / "compiled_artifacts.json"),
    }


def ikun_artifact_rows(conn: sqlite3.Connection, corpus: str) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM ikun_artifacts WHERE corpus = ? ORDER BY context_id, artifact_type", (corpus,)))


def ikun_select_artifacts(conn: sqlite3.Connection, corpus: str, query: dict[str, Any]) -> tuple[list[sqlite3.Row], list[str]]:
    requested_contexts = [str(item) for item in query.get("contexts", [])] or list(IKUN_CONTEXTS)
    where = query.get("where") if isinstance(query.get("where"), dict) else {}
    artifacts = []
    warnings: list[str] = []
    for context_id in requested_contexts:
        if context_id not in IKUN_CONTEXTS:
            warnings.append(f"unknown_context:{context_id}")
    known_contexts = {context for context in requested_contexts if context in IKUN_CONTEXTS}
    artifact_types = set(where.get("artifact_types") or [])
    if where.get("artifact_type"):
        artifact_types.add(str(where["artifact_type"]))
    filters = {
        "run_id": str(where.get("run_id", "")).strip(),
        "task_id": str(where.get("task_id", "")).strip(),
        "category": str(where.get("i_category", where.get("category", ""))).strip(),
        "role": str(where.get("role", "")).strip(),
        "business_domain": str(where.get("business_domain", "")).strip(),
    }
    for row in ikun_artifact_rows(conn, corpus):
        if known_contexts and row["context_id"] not in known_contexts:
            continue
        if artifact_types and row["artifact_type"] not in artifact_types:
            continue
        data_text = json_dumps(row_json(row, "data_json", {})).lower()
        if any(value and value.lower() not in data_text for value in filters.values()):
            continue
        artifacts.append(row)
    if not artifacts:
        warnings.append("no_ikun_artifacts_selected")
    return artifacts, warnings


def ikun_citations_for_path(citations: dict[str, Any], path: str) -> list[dict[str, Any]]:
    if path in citations:
        return list(citations[path])
    if "." in path and path.split(".")[0] in citations:
        return list(citations[path.split(".")[0]])
    if "[" in path and path.split("[")[0] in citations:
        return list(citations[path.split("[")[0]])
    return []


def ikun_best_field(prop: str, query: dict[str, Any], artifacts: list[sqlite3.Row]) -> dict[str, Any] | None:
    best: tuple[float, sqlite3.Row, str, Any] | None = None
    ask = query.get("ask", "")
    for artifact in artifacts:
        data = row_json(artifact, "data_json", {})
        for path, value in flatten_json(data):
            if not path:
                continue
            exact = 50.0 if prop == path or path.endswith(f".{prop}") else 0.0
            prop_tokens = tokenize(prop.replace("_", " "))
            score = exact + score_text(prop_tokens, f"{path} {value} {artifact['title']}") * 2.0 + score_text(tokenize(ask), f"{path} {value}") * 0.08
            if best is None or score > best[0]:
                best = (score, artifact, path, value)
    if best is None:
        return None
    _, artifact, path, value = best
    citations = ikun_citations_for_path(row_json(artifact, "citations_json", {}), path)
    return {
        "value": value,
        "source_artifact": artifact["id"],
        "field_path": path,
        "context_id": artifact["context_id"],
        "artifact_type": artifact["artifact_type"],
        "confidence": artifact["confidence"],
        "citations": citations,
    }


def ikun_prepare_artifacts(artifacts: list[sqlite3.Row]) -> list[dict[str, Any]]:
    prepared = []
    for artifact in artifacts:
        data = row_json(artifact, "data_json", {})
        citations = row_json(artifact, "citations_json", {})
        flat = flatten_json(data)
        exact = {path: value for path, value in flat if path}
        prepared.append(
            {
                "row": artifact,
                "data": data,
                "citations": citations,
                "flat": flat,
                "exact": exact,
            }
        )
    return prepared


def ikun_best_field_prepared(prop: str, query: dict[str, Any], prepared: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in prepared:
        if prop in item["exact"]:
            artifact = item["row"]
            citations = ikun_citations_for_path(item["citations"], prop)
            return {
                "value": item["exact"][prop],
                "source_artifact": artifact["id"],
                "field_path": prop,
                "context_id": artifact["context_id"],
                "artifact_type": artifact["artifact_type"],
                "confidence": artifact["confidence"],
                "citations": citations,
            }
    best: tuple[float, dict[str, Any], str, Any] | None = None
    ask = query.get("ask", "")
    ask_tokens = tokenize(ask)
    prop_tokens = tokenize(prop.replace("_", " "))
    for item in prepared:
        artifact = item["row"]
        for path, value in item["flat"]:
            if not path:
                continue
            exact = 45.0 if path.endswith(f".{prop}") else 0.0
            score = exact + score_text(prop_tokens, f"{path} {value} {artifact['title']}") * 2.0 + score_text(ask_tokens, f"{path} {value}") * 0.05
            if best is None or score > best[0]:
                best = (score, item, path, value)
    if best is None:
        return None
    _, item, path, value = best
    artifact = item["row"]
    return {
        "value": value,
        "source_artifact": artifact["id"],
        "field_path": path,
        "context_id": artifact["context_id"],
        "artifact_type": artifact["artifact_type"],
        "confidence": artifact["confidence"],
        "citations": ikun_citations_for_path(item["citations"], path),
    }


def ikun_source_prefix_filter(query: dict[str, Any]) -> str:
    where = query.get("where") if isinstance(query.get("where"), dict) else {}
    for key in ["source_path_prefix", "path_prefix", "source_prefix"]:
        if where.get(key):
            return str(where[key]).replace("\\", "/").strip("/")
    return ""


def ikun_query_terms(query: dict[str, Any]) -> list[str]:
    props = (query.get("shape") or {}).get("properties", {}) if isinstance(query.get("shape"), dict) else {}
    terms = tokenize(query.get("ask", "") + " " + " ".join(props.keys()))
    where = query.get("where") if isinstance(query.get("where"), dict) else {}
    for key in ["run_id", "task_id", "i_category", "role", "business_domain"]:
        if where.get(key):
            terms.extend(tokenize(str(where[key])))
    return terms


def run_ikun_compiled_query(conn: sqlite3.Connection, query: dict[str, Any], corpus: str = IKUN_CORPUS_ID) -> dict[str, Any]:
    init_schema(conn)
    errors = validate_query(query)
    if errors:
        raise KnowledgeError("; ".join(errors))
    if conn.execute("SELECT COUNT(*) AS n FROM ikun_artifacts WHERE corpus = ?", (corpus,)).fetchone()["n"] == 0:
        raise KnowledgeError(f"No ikunAim artifacts for corpus {corpus}. Run ikun-compile first.")
    start = time.perf_counter()
    artifacts, warnings = ikun_select_artifacts(conn, corpus, query)
    shape = query.get("shape") if isinstance(query.get("shape"), dict) else {}
    props = shape.get("properties") if isinstance(shape.get("properties"), dict) else {}
    prefix = ikun_source_prefix_filter(query)
    fields: dict[str, Any] = {}
    answer: dict[str, Any] = {}
    citations: list[dict[str, Any]] = []
    prepared = ikun_prepare_artifacts(artifacts)
    if props:
        for prop in props:
            found = ikun_best_field_prepared(prop, query, prepared)
            if found is None:
                fields[prop] = {"value": None, "source_artifact": None, "field_path": None, "confidence": 0.0, "citations": []}
                answer[prop] = None
                warnings.append(f"field_unresolved:{prop}")
                continue
            if prefix:
                found["citations"] = [citation for citation in found["citations"] if str(citation.get("path", "")).startswith(prefix)]
                if not found["citations"]:
                    warnings.append(f"source_path_prefix_filtered_citation:{prop}")
            fields[prop] = found
            answer[prop] = found["value"]
            citations.extend(found["citations"])
    else:
        answer["artifacts"] = []
        for row in artifacts:
            data = row_json(row, "data_json", {})
            art_citations = row_json(row, "citations_json", {})
            if prefix and not any(str(citation.get("path", "")).startswith(prefix) for values in art_citations.values() for citation in values):
                continue
            answer["artifacts"].append(
                {
                    "id": row["id"],
                    "context_id": row["context_id"],
                    "artifact_type": row["artifact_type"],
                    "title": row["title"],
                    "data": data,
                }
            )
            for values in art_citations.values():
                citations.extend(values)
    if query.get("ground", False) and props:
        for prop, field in fields.items():
            if not field["citations"]:
                warnings.append(f"missing_citation:{prop}")
    deduped = []
    seen = set()
    for citation in citations:
        key = (citation.get("path"), citation.get("line_start"), citation.get("field_path"), citation.get("quote"))
        if key not in seen:
            seen.add(key)
            deduped.append(citation)
    confidence_values = [row["confidence"] for row in artifacts]
    latency_ms = (time.perf_counter() - start) * 1000.0
    served_payload = {"answer": answer, "citations": deduped}
    return {
        "answer": answer,
        "fields": fields,
        "citations": deduped,
        "confidence": {
            "aggregate": round(min(confidence_values), 3) if confidence_values else 0.0,
            "selected_artifact_count": len(artifacts),
        },
        "budget_used": {
            "latency_ms": round(latency_ms, 3),
            "depth": "compiled",
            "artifacts": len(artifacts),
            "source_bytes_proxy": len(json_dumps(served_payload).encode("utf-8")),
            "steps": 1 if artifacts else 0,
        },
        "filtered_by_acl": False,
        "warnings": warnings,
    }


def run_ikun_coding_sandbox_query(conn: sqlite3.Connection, query: dict[str, Any], corpus: str = IKUN_CORPUS_ID) -> dict[str, Any]:
    start = time.perf_counter()
    terms = ikun_query_terms(query)
    prefix = ikun_source_prefix_filter(query)
    rows = list(conn.execute("SELECT * FROM ikun_sources WHERE corpus = ? ORDER BY noisy, rel_path", (corpus,)))
    if prefix:
        rows = [row for row in rows if row["rel_path"].startswith(prefix)]
    scored = []
    for row in rows:
        haystack = f"{row['rel_path']} {row['content']}".lower()
        score = sum(1 for term in terms if term in haystack)
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda item: (item[0], -int(item[1]["noisy"]), -int(item[1]["byte_count"])), reverse=True)
    selected = [row for _, row in scored[:10]]
    snippets = []
    source_bytes = 0
    steps = 0
    for row in selected:
        content = row["content"]
        source_bytes += int(row["byte_count"])
        steps += 1
        lowered = content.lower()
        snippet = content[:800]
        for term in terms[:16]:
            steps += 1
            index = lowered.find(term)
            if index >= 0:
                snippet = content[max(0, index - 350) : min(len(content), index + 750)]
                break
        snippets.append({"path": row["rel_path"], "snippet": re.sub(r"\s+", " ", snippet).strip()[:1400]})
    latency_ms = (time.perf_counter() - start) * 1000.0
    return {
        "answer": {"snippets": snippets},
        "fields": {},
        "citations": [],
        "confidence": {"aggregate": 0.0, "selected_artifact_count": 0},
        "budget_used": {
            "latency_ms": round(latency_ms, 3),
            "depth": "coding_sandbox",
            "artifacts": 0,
            "source_bytes_proxy": source_bytes,
            "steps": max(1, steps),
        },
        "filtered_by_acl": False,
        "warnings": ["coding_sandbox_simulates_file_search_read_and_manual_composition"],
    }


def run_ikun_agentic_rag_query(conn: sqlite3.Connection, query: dict[str, Any], corpus: str = IKUN_CORPUS_ID) -> dict[str, Any]:
    start = time.perf_counter()
    terms = ikun_query_terms(query)
    prefix = ikun_source_prefix_filter(query)
    expansions = [escape_fts_query(terms[:8])]
    if prefix:
        expansions.append(escape_fts_query(tokenize(prefix.replace("/", " "))))
    if "audit" in query.get("ask", "").lower() or "故障" in query.get("ask", ""):
        expansions.append('"defect" OR "event" OR "ledger" OR "validation" OR "audit"')
    if "business" in query.get("ask", "").lower() or "业务" in query.get("ask", ""):
        expansions.append('"business" OR "scrcpy" OR "Android" OR "AI"')
    scored: dict[str, tuple[float, sqlite3.Row, str]] = {}
    for ranker, fts_query in enumerate(expansions):
        try:
            rows = list(
                conn.execute(
                    """
                    SELECT c.*, snippet(ikun_chunk_fts, 3, '[', ']', ' ... ', 32) AS snippet
                    FROM ikun_chunk_fts
                    JOIN ikun_chunks c ON c.id = ikun_chunk_fts.chunk_id
                    WHERE ikun_chunk_fts MATCH ? AND c.corpus = ?
                    LIMIT 20
                    """,
                    (fts_query, corpus),
                )
            )
        except sqlite3.OperationalError:
            rows = []
        for rank, row in enumerate(rows, start=1):
            if prefix and not row["rel_path"].startswith(prefix):
                continue
            current = scored.get(row["id"], (0.0, row, ""))[0]
            snippet = row["snippet"] if "snippet" in row.keys() and row["snippet"] else row["text"][:900]
            scored[row["id"]] = (current + 1.0 / (rank + 60 + ranker), row, snippet)
    selected = sorted(scored.values(), key=lambda item: item[0], reverse=True)[:24]
    snippets = []
    source_bytes = 0
    for _, row, snippet in selected:
        source_bytes += int(row["byte_count"])
        snippets.append(
            {
                "path": row["rel_path"],
                "line_start": row["line_start"],
                "line_end": row["line_end"],
                "snippet": re.sub(r"\s+", " ", snippet).strip()[:1400],
            }
        )
    latency_ms = (time.perf_counter() - start) * 1000.0
    return {
        "answer": {"snippets": snippets},
        "fields": {},
        "citations": [],
        "confidence": {"aggregate": 0.0, "selected_artifact_count": 0},
        "budget_used": {
            "latency_ms": round(latency_ms, 3),
            "depth": "agentic_rag",
            "artifacts": 0,
            "source_bytes_proxy": source_bytes,
            "steps": max(1, len(expansions) + len(selected)),
        },
        "filtered_by_acl": False,
        "warnings": ["agentic_rag_returns_ranked_chunks_not_typed_artifacts"],
    }


def run_ikun_retriever(conn: sqlite3.Connection, retriever: str, query: dict[str, Any], corpus: str) -> dict[str, Any]:
    if retriever == "compiled":
        return run_ikun_compiled_query(conn, query, corpus)
    if retriever == "agentic_rag":
        return run_ikun_agentic_rag_query(conn, query, corpus)
    if retriever in {"coding_sandbox", "coding_agent"}:
        return run_ikun_coding_sandbox_query(conn, query, corpus)
    raise KnowledgeError(f"unknown ikun retriever: {retriever}")


def ikun_eval_query(question: str, contexts: list[str], fields: list[str], category: str, corpus: str, where: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ask": question,
        "contexts": contexts,
        "where": {"principal_tags": ["public"], **(where or {})},
        "ground": True,
        "shape": {"type": "object", "properties": {field: {"type": "string"} for field in fields}},
        "confidence": {"min": 0.6},
        "budget": {"depth": "standard", "latency_ms": 120000, "category": category, "corpus": corpus},
    }


def ikun_required_contains(artifact_data: dict[str, Any], fields: list[str]) -> list[str]:
    def value_terms(value: Any) -> list[str]:
        if isinstance(value, list):
            terms: list[str] = []
            for item in value[:3]:
                terms.extend(value_terms(item))
            return terms
        if isinstance(value, dict):
            return list(value.keys())[:3]
        if value in (None, ""):
            return []
        text = re.sub(r"\s+", " ", str(value)).strip()
        semantic: list[str] = []
        for pattern in [r"run_[A-Za-z0-9_]+", r"TASK-[0-9-]+", r"I[0-9]", r"mobile-touch", r"QtScrcpy", r"scrcpy", r"Android", r"writeback", r"validation", r"read-only", r"只读", r"Pro", r"current_run"]:
            for match in re.findall(pattern, text, flags=re.IGNORECASE):
                if match not in semantic:
                    semantic.append(match)
        if semantic:
            return semantic[:4]
        if len(text) > 80:
            tokens = [token for token in tokenize(text) if len(token) >= 4]
            return tokens[:3] or [text[:60]]
        return [text]

    terms: list[str] = []
    for field in fields:
        terms.extend(value_terms(artifact_data.get(field)))
    clean = []
    for term in terms:
        term = re.sub(r"\s+", " ", term).strip()
        if term and term.lower() not in {item.lower() for item in clean}:
            clean.append(term[:120])
    return clean[:5]


def ikun_eval_case_specs(conn: sqlite3.Connection, corpus: str, limit: int = 90) -> list[dict[str, Any]]:
    artifacts = {row["artifact_type"]: row_json(row, "data_json", {}) for row in ikun_artifact_rows(conn, corpus)}
    if not artifacts:
        raise KnowledgeError(f"No ikun artifacts for {corpus}. Run ikun-compile first.")
    workflow = artifacts.get("workflow_control", {})
    profile = artifacts.get("project_profile", {})
    role_gate = artifacts.get("role_gate", {})
    memory = artifacts.get("memory_system", {})
    runs = artifacts.get("run_history", {})
    pro = artifacts.get("pro_feedback", {})
    business = artifacts.get("business_context", {})
    cases: list[dict[str, Any]] = []

    workflow_templates = [
        ("What is the mandatory execution loop for ikunAim and which current run is it attached to?", ["mandatory_loop", "current_run_id", "current_task_id"], ["ikunaim_workflow", "ikunaim_runs"], workflow),
        ("Which validation gates and stop rule govern a workflow task?", ["validation_gates", "stop_rule", "red_lines"], ["ikunaim_workflow"], workflow),
        ("How should the role gate classify I0-I9 work before execution?", ["role_gate_mode", "task_categories", "gate_rule"], ["ikunaim_workflow"], role_gate),
        ("What does current_run.yaml say about the latest task pointer?", ["current_run_id", "current_task_id", "run_status"], ["ikunaim_workflow", "ikunaim_runs"], workflow),
        ("Which trusted initial sources should be used to resume the current run?", ["trusted_initial_sources", "current_run_id"], ["ikunaim_workflow"], workflow),
    ]
    for index in range(30):
        question, fields, contexts, data = workflow_templates[index % len(workflow_templates)]
        cases.append(
            {
                "id": f"ikun_wf_{index + 1:03d}",
                "suite": IKUN_SUITE_NAME,
                "category": "cross_document_workflow",
                "question": f"{question} Variant {index // len(workflow_templates) + 1}.",
                "query": ikun_eval_query(question, contexts, fields, "cross_document_workflow", corpus),
                "expected": {"contains": ikun_required_contains(data, fields), "required_fields": fields, "grounded": True},
            }
        )

    audit_templates = [
        ("How do we audit the latest run without trusting stale current_run state?", ["current_run_id", "latest_runs", "stale_current_run_risk"], ["ikunaim_runs", "ikunaim_workflow"], runs),
        ("Which files or ledgers should be checked for defects and events?", ["defect_event_sources", "task_index_sources"], ["ikunaim_runs"], runs),
        ("What handoff and validation evidence exists in run history?", ["handoff_sources", "validation_gates"], ["ikunaim_runs", "ikunaim_workflow"], {**runs, **workflow}),
        ("How should Pro feedback close through audit rather than direct writeback?", ["external_feedback_intake", "audit_closure", "absorption_status"], ["ikunaim_pro"], pro),
        ("Where is the visible-send confirmation guard repair represented?", ["visible_send_guard", "current_run_id", "current_task_id"], ["ikunaim_pro", "ikunaim_runs"], {**pro, **runs}),
    ]
    for index in range(25):
        question, fields, contexts, data = audit_templates[index % len(audit_templates)]
        cases.append(
            {
                "id": f"ikun_audit_{index + 1:03d}",
                "suite": IKUN_SUITE_NAME,
                "category": "failure_audit_chain",
                "question": f"{question} Audit slice {index // len(audit_templates) + 1}.",
                "query": ikun_eval_query(question, contexts, fields, "failure_audit_chain", corpus),
                "expected": {"contains": ikun_required_contains(data, fields), "required_fields": fields, "grounded": True},
            }
        )

    business_templates = [
        ("What is ikunAim's business direction and product domain?", ["business_direction", "business_domains"], ["ikunaim_business"], {**profile, **business}),
        ("What is the read-only boundary for the old mobile-touch project?", ["old_project_boundary", "legacy_reference_policy"], ["ikunaim_business"], {**business, **profile}),
        ("Which reference materials are included and why are they noisy?", ["reference_text_sources", "privacy_noise_note"], ["ikunaim_business"], business),
        ("What is the stage-1 no-migration policy?", ["no_migration_policy", "success_boundary"], ["ikunaim_business"], {**business, **profile}),
    ]
    for index in range(20):
        question, fields, contexts, data = business_templates[index % len(business_templates)]
        cases.append(
            {
                "id": f"ikun_business_{index + 1:03d}",
                "suite": IKUN_SUITE_NAME,
                "category": "business_boundary",
                "question": f"{question} Business pass {index // len(business_templates) + 1}.",
                "query": ikun_eval_query(question, contexts, fields, "business_boundary", corpus),
                "expected": {"contains": ikun_required_contains(data, fields), "required_fields": fields, "grounded": True},
            }
        )

    decision_templates = [
        ("If a new task touches old project materials, which workflow, role, memory, and business constraints apply?", ["mandatory_loop", "gate_rule", "writeback_boundary", "old_project_boundary"], ["ikunaim_workflow", "ikunaim_memory", "ikunaim_business"], {**workflow, **role_gate, **memory, **business}),
        ("If Pro suggests changing project rules, what is the correct absorption and validation path?", ["external_feedback_intake", "absorption_status", "validation_gates", "writeback_boundary"], ["ikunaim_pro", "ikunaim_workflow", "ikunaim_memory"], {**pro, **workflow, **memory}),
        ("To resume work safely, which current run, task, role gate, and run-history evidence should be consulted?", ["current_run_id", "current_task_id", "role_gate_mode", "latest_runs"], ["ikunaim_workflow", "ikunaim_runs"], {**workflow, **role_gate, **runs}),
    ]
    for index in range(15):
        question, fields, contexts, data = decision_templates[index % len(decision_templates)]
        cases.append(
            {
                "id": f"ikun_decision_{index + 1:03d}",
                "suite": IKUN_SUITE_NAME,
                "category": "integrated_decision",
                "question": f"{question} Decision case {index // len(decision_templates) + 1}.",
                "query": ikun_eval_query(question, contexts, fields, "integrated_decision", corpus),
                "expected": {"contains": ikun_required_contains(data, fields), "required_fields": fields, "grounded": True},
            }
        )
    return cases[:limit]


def ikun_adaptive_case_specs(conn: sqlite3.Connection, corpus: str, limit: int = 40) -> list[dict[str, Any]]:
    artifacts = {row["artifact_type"]: row_json(row, "data_json", {}) for row in ikun_artifact_rows(conn, corpus)}
    if not artifacts:
        raise KnowledgeError(f"No ikun artifacts for {corpus}. Run ikun-compile first.")
    workflow = artifacts.get("workflow_control", {})
    role_gate = artifacts.get("role_gate", {})
    memory = artifacts.get("memory_system", {})
    runs = artifacts.get("run_history", {})
    pro = artifacts.get("pro_feedback", {})
    business = artifacts.get("business_context", {})
    cases: list[dict[str, Any]] = []

    intake_templates = [
        (
            "A user says: 'Pro auto-send looks unsafe after the last failure; decide the workflow route before touching browser automation.' What route, stop rule, and validation gates apply?",
            ["task_categories", "gate_rule", "stop_rule", "validation_gates"],
            ["ikunaim_workflow"],
            {**role_gate, **workflow},
            {},
        ),
        (
            "A user says: 'Move old mobile-touch material into the new project if useful.' What adaptive route should prevent unsafe migration?",
            ["task_categories", "gate_rule", "old_project_boundary", "no_migration_policy"],
            ["ikunaim_workflow", "ikunaim_business"],
            {**role_gate, **business},
            {},
        ),
        (
            "A user says: 'Add a new workflow rule based on a Pro comment.' Which intake route and absorption rules should be used before any writeback?",
            ["task_categories", "external_feedback_intake", "absorption_status", "writeback_boundary"],
            ["ikunaim_workflow", "ikunaim_pro", "ikunaim_memory"],
            {**role_gate, **pro, **memory},
            {},
        ),
        (
            "A user says: 'The next task is just a business direction question about Android control.' Which business domain and role-gate constraints should be selected?",
            ["business_domains", "business_direction", "role_gate_mode", "gate_rule"],
            ["ikunaim_business", "ikunaim_workflow"],
            {**business, **role_gate},
            {},
        ),
        (
            "A user says: 'Resume the project from wherever it stopped.' What current pointers and run-history checks should adaptive routing consult?",
            ["current_run_id", "current_task_id", "run_status", "stale_current_run_risk"],
            ["ikunaim_runs", "ikunaim_workflow"],
            {**workflow, **runs},
            {},
        ),
    ]
    for index in range(10):
        question, fields, contexts, data, where = intake_templates[index % len(intake_templates)]
        cases.append(
            {
                "id": f"ikun_adapt_intake_{index + 1:03d}",
                "suite": IKUN_ADAPTIVE_SUITE_NAME,
                "category": "adaptive_intake_routing",
                "question": f"{question} Intake scenario {index // len(intake_templates) + 1}.",
                "query": ikun_eval_query(question, contexts, fields, "adaptive_intake_routing", corpus, where),
                "expected": {"contains": ikun_required_contains(data, fields), "required_fields": fields, "grounded": True},
            }
        )

    role_templates = [
        (
            "The task touches workflow engine rules, prompt design, and validation. Which role/domain routing facts stop one role from self-signing?",
            ["role_gate_mode", "business_domains", "base_roles", "gate_rule"],
            ["ikunaim_workflow", "ikunaim_business"],
            {**role_gate, **business},
            {},
        ),
        (
            "A workflow refactor changes I0-I9 routing. What classification and validation facts must be selected before executing?",
            ["task_categories", "validation_gates", "gate_rule", "red_lines"],
            ["ikunaim_workflow"],
            {**role_gate, **workflow},
            {},
        ),
        (
            "A prompt/interaction change affects Pro handoff wording. Which adaptive role-gate and Pro-intake fields should guide the task?",
            ["business_domains", "gate_rule", "external_feedback_intake", "validation_gates"],
            ["ikunaim_workflow", "ikunaim_pro", "ikunaim_business"],
            {**role_gate, **workflow, **pro, **business},
            {},
        ),
        (
            "A state checker change updates ledgers and mirrors. Which routing facts identify state/audit ownership and evidence sources?",
            ["business_domains", "defect_event_sources", "task_index_sources", "validation_gates"],
            ["ikunaim_workflow", "ikunaim_runs"],
            {**role_gate, **runs, **workflow},
            {},
        ),
        (
            "A memory writeback request appears after a run closes. Which role and memory boundaries should adaptive routing enforce?",
            ["writeback_boundary", "writeback_queue_sources", "gate_rule", "validation_gates"],
            ["ikunaim_memory", "ikunaim_workflow"],
            {**memory, **role_gate, **workflow},
            {},
        ),
    ]
    for index in range(10):
        question, fields, contexts, data, where = role_templates[index % len(role_templates)]
        cases.append(
            {
                "id": f"ikun_adapt_role_{index + 1:03d}",
                "suite": IKUN_ADAPTIVE_SUITE_NAME,
                "category": "adaptive_role_domain_selection",
                "question": f"{question} Role scenario {index // len(role_templates) + 1}.",
                "query": ikun_eval_query(question, contexts, fields, "adaptive_role_domain_selection", corpus, where),
                "expected": {"contains": ikun_required_contains(data, fields), "required_fields": fields, "grounded": True},
            }
        )

    recovery_templates = [
        (
            "The workflow checker says current_run may be stale. What adaptive recovery path should verify before continuing?",
            ["current_run_id", "latest_runs", "stale_current_run_risk", "defect_event_sources"],
            ["ikunaim_runs"],
            runs,
            {},
        ),
        (
            "A Pro send/capture task fails confidence validation. What stop, validation, and audit facts block continuing?",
            ["stop_rule", "validation_gates", "visible_send_guard", "audit_closure"],
            ["ikunaim_workflow", "ikunaim_pro"],
            {**workflow, **pro},
            {},
        ),
        (
            "A path/encoding parse issue affects workflow records. What ledgers and gates should route the repair before new work?",
            ["defect_event_sources", "validation_gates", "current_run_id", "current_task_id"],
            ["ikunaim_runs", "ikunaim_workflow"],
            {**runs, **workflow},
            {},
        ),
        (
            "A run has handoff evidence but validation is ambiguous. Which evidence sources and gates should adaptive recovery read?",
            ["handoff_sources", "validation_gates", "task_index_sources", "stale_current_run_risk"],
            ["ikunaim_runs", "ikunaim_workflow"],
            {**runs, **workflow},
            {},
        ),
    ]
    for index in range(8):
        question, fields, contexts, data, where = recovery_templates[index % len(recovery_templates)]
        cases.append(
            {
                "id": f"ikun_adapt_recovery_{index + 1:03d}",
                "suite": IKUN_ADAPTIVE_SUITE_NAME,
                "category": "adaptive_failure_recovery",
                "question": f"{question} Recovery scenario {index // len(recovery_templates) + 1}.",
                "query": ikun_eval_query(question, contexts, fields, "adaptive_failure_recovery", corpus, where),
                "expected": {"contains": ikun_required_contains(data, fields), "required_fields": fields, "grounded": True},
            }
        )

    pro_templates = [
        (
            "Pro returns P0/P1/P2 advice about adaptive agents workflow construction. What path keeps it external until locally accepted?",
            ["external_feedback_intake", "absorption_status", "audit_closure", "writeback_boundary"],
            ["ikunaim_pro", "ikunaim_memory"],
            {**pro, **memory},
            {},
        ),
        (
            "Pro recommends event-led state and MAP-style routing. Which adaptive workflow facts decide whether it becomes backlog, run work, or memory?",
            ["external_feedback_intake", "validation_gates", "writeback_boundary", "task_index_sources"],
            ["ikunaim_pro", "ikunaim_workflow", "ikunaim_memory", "ikunaim_runs"],
            {**pro, **workflow, **memory, **runs},
            {},
        ),
        (
            "A Pro confidence loop asks to publish and then audit latest workflow state. What current run and audit closure facts should be cited?",
            ["current_run_id", "run_status", "audit_closure", "visible_send_guard"],
            ["ikunaim_runs", "ikunaim_pro"],
            {**runs, **workflow, **pro},
            {},
        ),
    ]
    for index in range(6):
        question, fields, contexts, data, where = pro_templates[index % len(pro_templates)]
        cases.append(
            {
                "id": f"ikun_adapt_pro_{index + 1:03d}",
                "suite": IKUN_ADAPTIVE_SUITE_NAME,
                "category": "adaptive_pro_absorption",
                "question": f"{question} Pro scenario {index // len(pro_templates) + 1}.",
                "query": ikun_eval_query(question, contexts, fields, "adaptive_pro_absorption", corpus, where),
                "expected": {"contains": ikun_required_contains(data, fields), "required_fields": fields, "grounded": True},
            }
        )

    memory_templates = [
        (
            "A completed run suggests a reusable workflow preference. How should adaptive routing decide memory eligibility?",
            ["writeback_boundary", "writeback_queue_sources", "latest_runs", "validation_gates"],
            ["ikunaim_memory", "ikunaim_runs", "ikunaim_workflow"],
            {**memory, **runs, **workflow},
            {},
        ),
        (
            "A temporary capture contains useful text but may be noisy. Which business/memory boundary prevents polluted long-term memory?",
            ["privacy_noise_note", "writeback_boundary", "reference_text_sources", "old_project_boundary"],
            ["ikunaim_business", "ikunaim_memory"],
            {**business, **memory},
            {},
        ),
        (
            "A dependency should be discovered during real tasks, not copied from old tools. Which routing and business boundary facts support that?",
            ["gate_rule", "business_domains", "old_project_boundary", "no_migration_policy"],
            ["ikunaim_workflow", "ikunaim_business"],
            {**role_gate, **business},
            {},
        ),
    ]
    for index in range(6):
        question, fields, contexts, data, where = memory_templates[index % len(memory_templates)]
        cases.append(
            {
                "id": f"ikun_adapt_memory_{index + 1:03d}",
                "suite": IKUN_ADAPTIVE_SUITE_NAME,
                "category": "adaptive_memory_and_boundary",
                "question": f"{question} Memory scenario {index // len(memory_templates) + 1}.",
                "query": ikun_eval_query(question, contexts, fields, "adaptive_memory_and_boundary", corpus, where),
                "expected": {"contains": ikun_required_contains(data, fields), "required_fields": fields, "grounded": True},
            }
        )
    return cases[:limit]


def seed_ikun_eval_cases(conn: sqlite3.Connection, suite: str, corpus: str, limit: int = 90) -> dict[str, Any]:
    if suite == IKUN_SUITE_NAME:
        return seed_case_specs(conn, suite, ikun_eval_case_specs(conn, corpus, limit), limit)
    if suite == IKUN_ADAPTIVE_SUITE_NAME:
        return seed_case_specs(conn, suite, ikun_adaptive_case_specs(conn, corpus, limit), limit)
    raise KnowledgeError(f"unknown ikun suite: {suite}")


def score_ikun_result(result: dict[str, Any], expected: dict[str, Any], retriever: str) -> tuple[bool, float, float]:
    text = answer_text(result)
    terms = [term for term in expected.get("contains", []) if str(term).strip()]
    term_hits = sum(1 for term in terms if str(term).lower()[:80] in text)
    term_score = term_hits / max(1, len(terms))
    if retriever == "compiled":
        fields = result.get("fields", {})
        required = expected.get("required_fields", [])
        field_hits = sum(1 for field in required if fields.get(field, {}).get("value") not in (None, "", []))
        grounded_hits = sum(1 for field in required if fields.get(field, {}).get("citations"))
        field_score = field_hits / max(1, len(required))
        citation_coverage = grounded_hits / max(1, len(required))
    else:
        field_score = 1.0 if result.get("answer", {}).get("snippets") else 0.0
        citation_coverage = 0.0
    score = round(term_score * 0.50 + field_score * 0.32 + citation_coverage * 0.18, 4)
    return score >= 0.75 and (retriever != "compiled" or citation_coverage >= 0.99), score, citation_coverage


def classify_ikun_failure(result: dict[str, Any], expected: dict[str, Any], retriever: str, citation_coverage: float) -> str:
    text = answer_text(result)
    if retriever == "compiled" and citation_coverage < 0.99:
        return "citation_missing"
    if "current_run" in text and any("current_run" in str(term).lower() for term in expected.get("contains", [])):
        return "stale_current_run"
    if retriever != "compiled" and not result.get("answer", {}).get("snippets"):
        return "missing_fact"
    missing = [str(term) for term in expected.get("contains", []) if str(term).lower()[:80] not in text]
    if any(re.search(r"TASK-|run_", term) for term in missing):
        return "wrong_run_or_task"
    if any(re.fullmatch(r"I[0-9]", term) for term in missing):
        return "wrong_policy_level"
    if any("scrcpy" in term.lower() or "android" in term.lower() for term in missing):
        return "ambiguous_business_boundary"
    if any("encoding" in str(warning) for warning in result.get("warnings", [])):
        return "encoding_parse_failure"
    if any("temp" in text or "reference_materials" in text for _ in [0]) and missing:
        return "noisy_temp_capture"
    return "missing_fact" if missing else "judge_disagreement"


def ikun_corpus_profile(conn: sqlite3.Connection, corpus: str) -> dict[str, Any]:
    source_count = conn.execute("SELECT COUNT(*) AS n FROM ikun_sources WHERE corpus = ?", (corpus,)).fetchone()["n"]
    artifact_count = conn.execute("SELECT COUNT(*) AS n FROM ikun_artifacts WHERE corpus = ?", (corpus,)).fetchone()["n"]
    chunk_count = conn.execute("SELECT COUNT(*) AS n FROM ikun_chunks WHERE corpus = ?", (corpus,)).fetchone()["n"]
    bytes_total = conn.execute("SELECT COALESCE(SUM(byte_count), 0) AS n FROM ikun_sources WHERE corpus = ?", (corpus,)).fetchone()["n"]
    suffix_counts = {
        row["suffix"]: row["n"]
        for row in conn.execute("SELECT suffix, COUNT(*) AS n FROM ikun_sources WHERE corpus = ? GROUP BY suffix ORDER BY suffix", (corpus,))
    }
    noisy_count = conn.execute("SELECT COUNT(*) AS n FROM ikun_sources WHERE corpus = ? AND noisy = 1", (corpus,)).fetchone()["n"]
    top_dirs = Counter()
    for row in conn.execute("SELECT rel_path FROM ikun_sources WHERE corpus = ?", (corpus,)):
        top_dirs[row["rel_path"].split("/", 1)[0]] += 1
    return {
        "sources": source_count,
        "artifacts": artifact_count,
        "chunks": chunk_count,
        "text_bytes": bytes_total,
        "text_mib": round(bytes_total / (1024 * 1024), 3),
        "suffix_counts": dict(sorted(suffix_counts.items())),
        "noisy_sources": noisy_count,
        "top_dirs": dict(sorted(top_dirs.items())),
    }


def run_ikun_eval(conn: sqlite3.Connection, suite: str, retrievers: list[str], corpus: str, limit: int = 90) -> dict[str, Any]:
    if suite not in IKUN_SUITE_NAMES:
        raise KnowledgeError(f"unknown ikun suite: {suite}")
    init_schema(conn)
    seed_ikun_eval_cases(conn, suite, corpus, limit)
    rows = list(conn.execute("SELECT * FROM eval_cases WHERE suite = ? ORDER BY category, id LIMIT ?", (suite, limit)))
    summaries: dict[str, Any] = {}
    run_rows = []
    for retriever in retrievers:
        results = []
        for row in rows:
            query = json_loads(row["query_json"], {})
            expected = json_loads(row["expected_json"], {})
            started = time.perf_counter()
            result = run_ikun_retriever(conn, retriever, query, corpus)
            latency_ms = (time.perf_counter() - started) * 1000.0
            passed, score, citation_coverage = score_ikun_result(result, expected, retriever)
            failure_category = "" if passed else classify_ikun_failure(result, expected, retriever, citation_coverage)
            budget = result.get("budget_used", {})
            source_bytes = int(budget.get("source_bytes_proxy", 0))
            steps = int(budget.get("steps", 1))
            run_rows.append(
                (
                    stable_id(suite, corpus, retriever, row["id"], utc_now(), length=24),
                    suite,
                    retriever,
                    row["id"],
                    1 if passed else 0,
                    score,
                    latency_ms,
                    source_bytes,
                    steps,
                    citation_coverage,
                    json_dumps(result),
                    utc_now(),
                )
            )
            results.append(
                {
                    "case_id": row["id"],
                    "category": row["category"],
                    "passed": passed,
                    "score": score,
                    "latency_ms": round(latency_ms, 3),
                    "source_bytes": source_bytes,
                    "steps": steps,
                    "citation_coverage": round(citation_coverage, 3),
                    "failure_category": failure_category,
                }
            )
        passed_count = sum(1 for item in results if item["passed"])
        latencies = sorted(item["latency_ms"] for item in results)
        failures = Counter(item["failure_category"] for item in results if item["failure_category"])
        summaries[retriever] = {
            "cases": len(results),
            "passed": passed_count,
            "completion_rate": round(passed_count / max(1, len(results)), 3),
            "average_score": round(sum(item["score"] for item in results) / max(1, len(results)), 4),
            "median_latency_ms": latencies[len(latencies) // 2] if latencies else 0,
            "total_source_bytes_proxy": sum(item["source_bytes"] for item in results),
            "average_steps": round(sum(item["steps"] for item in results) / max(1, len(results)), 3),
            "average_citation_coverage": round(sum(item["citation_coverage"] for item in results) / max(1, len(results)), 3),
            "failure_categories": dict(sorted(failures.items())),
            "results": results,
        }
    with conn:
        conn.executemany(
            """
            INSERT INTO eval_runs
              (id, suite, retriever, case_id, passed, score, latency_ms, source_bytes,
               steps, citation_coverage, answer_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            run_rows,
        )
    if "compiled" in summaries and "agentic_rag" in summaries:
        rag_bytes = max(1, summaries["agentic_rag"]["total_source_bytes_proxy"])
        comp_bytes = max(1, summaries["compiled"]["total_source_bytes_proxy"])
        summaries["comparison"] = {
            "compiled_vs_agentic_rag_source_byte_reduction_x": round(rag_bytes / comp_bytes, 3),
            "compiled_completion_target_met": summaries["compiled"]["completion_rate"] >= 0.9,
            "compiled_citation_target_met": summaries["compiled"]["average_citation_coverage"] >= 0.99,
            "compiled_steps_target_met": summaries["compiled"]["average_steps"] <= 2,
            "compiled_latency_target_met": summaries["compiled"]["median_latency_ms"] < summaries["agentic_rag"]["median_latency_ms"],
            "compiled_source_reduction_target_met": (rag_bytes / comp_bytes) >= 5,
        }
    return {"suite": suite, "corpus": corpus, "retrievers": retrievers, "corpus_profile": ikun_corpus_profile(conn, corpus), "summary": summaries}


def ikun_analysis_markdown(result: dict[str, Any]) -> str:
    summary = result.get("summary", {})
    profile = result.get("corpus_profile", {})
    retrievers = [name for name in result.get("retrievers", []) if name in summary]
    lines = [
        f"# ikunAim Nexus-like Evaluation: {result.get('corpus')}",
        "",
        f"- Generated at: {utc_now()}",
        f"- Suite: `{result.get('suite')}`",
        "- Corpus note: external `ikunAim` project read-only corpus; runtime outputs live in Meta_workflow only.",
        f"- Corpus size: {profile.get('sources', 0)} sources, {profile.get('artifacts', 0)} artifacts, "
        f"{profile.get('chunks', 0)} chunks, {profile.get('text_mib', 0)} MiB readable text.",
        f"- Noisy sources included: {profile.get('noisy_sources', 0)} (`temp/`, `reference_materials/`, Pro captures).",
        "",
        "## Corpus Profile",
        "",
        f"- Suffix counts: {json_dumps(profile.get('suffix_counts', {}))}",
        f"- Top directories: {json_dumps(profile.get('top_dirs', {}))}",
        "",
        "## Comparison Table",
        "",
        "| retriever | cases | passed | completion | avg score | median latency ms | total source bytes | avg steps | citation coverage |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for retriever in retrievers:
        item = summary[retriever]
        lines.append(
            "| {name} | {cases} | {passed} | {completion:.3f} | {score:.4f} | {latency} | {bytes} | {steps:.3f} | {citation:.3f} |".format(
                name=retriever,
                cases=item["cases"],
                passed=item["passed"],
                completion=item["completion_rate"],
                score=item["average_score"],
                latency=item["median_latency_ms"],
                bytes=item["total_source_bytes_proxy"],
                steps=item["average_steps"],
                citation=item["average_citation_coverage"],
            )
        )
    comparison = summary.get("comparison", {})
    lines.extend(["", "## Interpretation", ""])
    if "compiled" in summary:
        compiled = summary["compiled"]
        lines.append(
            f"1. Compiled artifacts completed {compiled['passed']}/{compiled['cases']} cases "
            f"({compiled['completion_rate']:.3f}) with citation coverage {compiled['average_citation_coverage']:.3f}."
        )
    if "agentic_rag" in summary and "compiled" in summary:
        rag = summary["agentic_rag"]
        compiled = summary["compiled"]
        lines.append(
            f"2. Compiled used {compiled['total_source_bytes_proxy']} source-byte proxy versus "
            f"{rag['total_source_bytes_proxy']} for agentic RAG "
            f"({comparison.get('compiled_vs_agentic_rag_source_byte_reduction_x', 0)}x reduction)."
        )
        lines.append(
            f"3. Median latency was {compiled['median_latency_ms']} ms for compiled and "
            f"{rag['median_latency_ms']} ms for agentic RAG."
        )
    if comparison:
        gates = ", ".join(f"{key}={value}" for key, value in comparison.items() if key.endswith("_target_met"))
        lines.append(f"4. Acceptance gates: {gates}.")
    lines.extend(["", "## Failure Categories", ""])
    for retriever in retrievers:
        failures = summary[retriever].get("failure_categories", {})
        rendered = ", ".join(f"{key}: {value}" for key, value in failures.items()) or "none"
        lines.append(f"- `{retriever}`: {rendered}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This is a Nexus/KRAFT-style local reproduction on a project corpus, not a Pinecone internal implementation.",
            "- Automatic scores measure typed completion, grounding, and retrieval budget. Blind judge accuracy is exported separately through `ikun-judge-pack` / `ikun-judge-import`.",
            "",
        ]
    )
    return "\n".join(lines)


def ikun_suite_analysis_paths(corpus: str, suite: str) -> tuple[Path, Path]:
    paths = ensure_ikun_runtime(corpus)
    if suite == IKUN_SUITE_NAME:
        return paths["comparison_summary"], paths["analysis_report"]
    safe_suite = re.sub(r"[^A-Za-z0-9_.-]+", "_", suite)
    return paths["base"] / f"comparison_summary.{safe_suite}.json", paths["base"] / f"analysis_report.{safe_suite}.md"


def write_ikun_analysis_outputs(corpus: str, result: dict[str, Any]) -> dict[str, str]:
    comparison_path, report_path = ikun_suite_analysis_paths(corpus, str(result.get("suite", IKUN_SUITE_NAME)))
    write_json_file(comparison_path, result)
    report_path.write_text(ikun_analysis_markdown(result), encoding="utf-8")
    return {"comparison_summary": str(comparison_path), "analysis_report": str(report_path)}


def load_ikun_eval_cases(conn: sqlite3.Connection, suite: str, corpus: str, limit: int) -> list[sqlite3.Row]:
    if suite not in IKUN_SUITE_NAMES:
        raise KnowledgeError(f"unknown ikun suite: {suite}")
    seed_ikun_eval_cases(conn, suite, corpus, limit)
    return list(conn.execute("SELECT * FROM eval_cases WHERE suite = ? ORDER BY category, id LIMIT ?", (suite, limit)))


def ikun_agent_pack(args: argparse.Namespace) -> dict[str, Any]:
    retrievers = normalize_ikun_retrievers(args.retriever)
    paths = ensure_ikun_runtime(args.corpus)
    rows: list[dict[str, Any]] = []
    draft_answers: list[dict[str, Any]] = []
    with connect(Path(args.db)) as conn:
        init_schema(conn)
        cases = load_ikun_eval_cases(conn, args.suite, args.corpus, args.limit)
        for case in cases:
            query = json_loads(case["query_json"], {})
            for retriever in retrievers:
                evidence = run_ikun_retriever(conn, retriever, query, args.corpus)
                budget = evidence.get("budget_used", {})
                task_id = stable_id(args.suite, args.corpus, case["id"], retriever, length=24)
                rows.append(
                    {
                        "task_id": task_id,
                        "suite": args.suite,
                        "corpus": args.corpus,
                        "case_id": case["id"],
                        "category": case["category"],
                        "retriever": retriever,
                        "composer": args.composer,
                        "question": case["question"],
                        "retrieval_evidence": evidence,
                        "budget_used": {**budget, "token_proxy": token_proxy_from_budget(budget)},
                        "composer_instruction": (
                            "Answer using only retrieval_evidence. Return JSON with answer_text, citations, "
                            "completed, and uncertainty_notes. Do not use hidden ground truth."
                        ),
                    }
                )
                draft_answers.append(
                    {
                        "task_id": task_id,
                        "suite": args.suite,
                        "corpus": args.corpus,
                        "case_id": case["id"],
                        "retriever": retriever,
                        "composer": "draft_from_retriever_not_codex",
                        "completed": bool(answer_text(evidence).strip()),
                        "answer_text": answer_text(evidence)[:6000],
                        "citations": evidence.get("citations", []),
                        "budget_used": {**budget, "token_proxy": token_proxy_from_budget(budget)},
                        "warnings": ["draft_answer_for_pipeline_smoke_only_not_blind_judge_accuracy"],
                    }
                )
    paths["agent_pack"].write_text("", encoding="utf-8")
    append_jsonl(paths["agent_pack"], rows)
    paths["agent_answers_draft"].write_text("", encoding="utf-8")
    append_jsonl(paths["agent_answers_draft"], draft_answers)
    return {
        "status": "ikun_agent_pack_written",
        "suite": args.suite,
        "corpus": args.corpus,
        "path": str(paths["agent_pack"]),
        "draft_answers_path": str(paths["agent_answers_draft"]),
        "tasks": len(rows),
        "retrievers": retrievers,
        "composer": args.composer,
    }


def normalize_ikun_agent_answer(row: dict[str, Any]) -> dict[str, Any]:
    retriever = normalize_ikun_retrievers(str(row.get("retriever", "")))[0]
    answer_value = row.get("answer_text", row.get("answer", ""))
    if isinstance(answer_value, (dict, list)):
        answer_value = json_dumps(answer_value)
    return {
        "task_id": str(row.get("task_id") or stable_id(str(row.get("suite", "")), str(row.get("case_id", "")), retriever, length=24)),
        "suite": str(row.get("suite", IKUN_SUITE_NAME)),
        "corpus": str(row.get("corpus", IKUN_CORPUS_ID)),
        "case_id": str(row.get("case_id", "")),
        "retriever": retriever,
        "composer": str(row.get("composer", "codex")),
        "completed": bool(row.get("completed", True)),
        "answer_text": str(answer_value),
        "citations": row.get("citations", []),
        "budget_used": row.get("budget_used", {}),
        "warnings": row.get("warnings", []),
    }


def ikun_agent_import(args: argparse.Namespace) -> dict[str, Any]:
    paths = ensure_ikun_runtime(args.corpus)
    source = Path(args.input)
    if not source.exists():
        raise KnowledgeError(f"ikun agent answer input missing: {source}")
    rows = [normalize_ikun_agent_answer(row) for row in read_jsonl(source)]
    if not rows:
        raise KnowledgeError(f"no ikun agent answers found in {source}")
    paths["agent_answers"].write_text("", encoding="utf-8")
    append_jsonl(paths["agent_answers"], rows)
    by_retriever = Counter(row["retriever"] for row in rows)
    return {"status": "ikun_agent_answers_imported", "path": str(paths["agent_answers"]), "answers": len(rows), "by_retriever": dict(sorted(by_retriever.items()))}


def ikun_blind_judge_pack(args: argparse.Namespace) -> dict[str, Any]:
    paths = ensure_ikun_runtime(args.corpus)
    if not paths["agent_answers"].exists():
        if paths["agent_answers_draft"].exists():
            paths["agent_answers"].write_text(paths["agent_answers_draft"].read_text(encoding="utf-8"), encoding="utf-8")
        else:
            raise KnowledgeError(f"agent answers missing: {paths['agent_answers']}. Run ikun-agent-pack and ikun-agent-import first.")
    answers_by_case = grouped_agent_answers(paths["agent_answers"])
    key: dict[str, dict[str, str]] = {}
    rows: list[dict[str, Any]] = []
    with connect(Path(args.db)) as conn:
        init_schema(conn)
        cases = load_ikun_eval_cases(conn, args.suite, args.corpus, args.limit)
        for case in cases:
            expected = json_loads(case["expected_json"], {})
            answers = []
            for answer in answers_by_case.get(case["id"], []):
                answer_id = stable_id(args.suite, case["id"], answer["retriever"], "ikun-blind", length=16)
                key[answer_id] = {"case_id": case["id"], "retriever": answer["retriever"]}
                answers.append(
                    {
                        "answer_id": answer_id,
                        "answer_text": answer.get("answer_text", ""),
                        "citations": answer.get("citations", []),
                        "completed": answer.get("completed", False),
                        "budget_used": answer.get("budget_used", {}),
                    }
                )
            rng = random.Random(int(stable_id(args.suite, case["id"], "ikun-judge-order", length=12), 16))
            rng.shuffle(answers)
            rows.append(
                {
                    "case_id": case["id"],
                    "category": case["category"],
                    "question": case["question"],
                    "ground_truth": expected,
                    "answers": answers,
                    "judge": args.judge,
                    "judge_instruction": (
                        "Blindly grade each answer for factual accuracy against ground_truth and citations. "
                        "Return JSONL with case_id and judgements: answer_id, passed, accuracy_score in [0,1], "
                        "failure_category, rationale. Failure categories include missing_fact, wrong_run_or_task, "
                        "wrong_policy_level, stale_current_run, citation_missing, encoding_parse_failure, "
                        "noisy_temp_capture, ambiguous_business_boundary, judge_disagreement."
                    ),
                }
            )
    out_path = Path(args.output) if args.output else paths["judge_pack_blind"]
    out_path.write_text("", encoding="utf-8")
    append_jsonl(out_path, rows)
    write_json_file(paths["judge_answer_key"], {"created_at": utc_now(), "suite": args.suite, "corpus": args.corpus, "key": key})
    return {"status": "ikun_blind_judge_pack_written", "path": str(out_path), "answer_key_path": str(paths["judge_answer_key"]), "cases": len(rows), "judge": args.judge}


def ikun_judge_import(args: argparse.Namespace) -> dict[str, Any]:
    paths = ensure_ikun_runtime(args.corpus)
    source = Path(args.input)
    if not source.exists():
        raise KnowledgeError(f"ikun judge result input missing: {source}")
    answer_key = load_json_file(paths["judge_answer_key"], {}).get("key", {})
    if not answer_key:
        raise KnowledgeError(f"blind answer key missing: {paths['judge_answer_key']}. Run ikun-judge-pack --blind first.")
    normalized = []
    for row in read_jsonl(source):
        case_id = str(row.get("case_id", ""))
        for item in extract_judgement_items(row):
            answer_id = str(item.get("answer_id", ""))
            mapping = answer_key.get(answer_id, {})
            if not mapping:
                continue
            accuracy_score = float(item.get("accuracy_score", 1.0 if bool_from_judge_value(item.get("passed", False)) else 0.0))
            normalized.append(
                {
                    "case_id": case_id or mapping.get("case_id", ""),
                    "answer_id": answer_id,
                    "retriever": mapping.get("retriever", ""),
                    "passed": bool_from_judge_value(item.get("passed", accuracy_score >= 0.5)),
                    "accuracy_score": max(0.0, min(1.0, accuracy_score)),
                    "failure_category": str(item.get("failure_category", "")),
                    "rationale": str(item.get("rationale", "")),
                    "judge": args.judge,
                }
            )
    if not normalized:
        raise KnowledgeError(f"no valid blinded ikun judgements found in {source}")
    paths["judge_results"].write_text("", encoding="utf-8")
    append_jsonl(paths["judge_results"], normalized)
    agent_answers = read_jsonl(paths["agent_answers"])
    summary = {
        "status": "ikun_judge_results_imported",
        "suite": args.suite,
        "corpus": args.corpus,
        "judge": args.judge,
        "results": summarize_judge_results(normalized, agent_answers),
    }
    write_json_file(paths["judge_summary"], summary)
    return {**summary, "path": str(paths["judge_results"]), "summary_path": str(paths["judge_summary"])}


def ikun_analysis(args: argparse.Namespace) -> dict[str, Any]:
    paths = ensure_ikun_runtime(args.corpus)
    comparison_path, report_path = ikun_suite_analysis_paths(args.corpus, args.suite)
    summary = load_json_file(comparison_path, {})
    judge_summary = load_json_file(paths["judge_summary"], {})
    if not summary:
        with connect(Path(args.db)) as conn:
            init_schema(conn)
            summary = run_ikun_eval(conn, args.suite, normalize_ikun_retrievers(args.compare), args.corpus, args.limit)
    outputs = write_ikun_analysis_outputs(args.corpus, summary)
    report = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    if judge_summary:
        with report_path.open("a", encoding="utf-8") as handle:
            handle.write("\n## Blind Judge Summary\n\n")
            handle.write("```json\n")
            handle.write(json.dumps(judge_summary.get("results", {}), ensure_ascii=False, indent=2, sort_keys=True))
            handle.write("\n```\n")
    return {"status": "ikun_analysis_written", "corpus": args.corpus, "analysis_outputs": outputs, "judge_summary_available": bool(judge_summary), "report_bytes": len(report.encode("utf-8"))}


def context_specs() -> list[dict[str, Any]]:
    return [
        {
            "id": "meta_project",
            "name": "Meta_workflow Project",
            "description": "Project identity, repository map, hard boundaries, and local work loop.",
            "artifact_types": ["project_identity", "repository_map", "hard_boundaries", "decision_placement", "work_loop"],
            "acl_tags": ["public"],
        },
        {
            "id": "architecture",
            "name": "Architecture",
            "description": "Product direction, engine subsystems, success criteria, and roadmap.",
            "artifact_types": ["engine_shape", "success_criteria", "roadmap"],
            "acl_tags": ["public"],
        },
        {
            "id": "methodology",
            "name": "MAP Methodology",
            "description": "MAP paper interpretation, module mapping, and planning principles.",
            "artifact_types": ["map_core", "map_modules", "map_extensions", "design_principles"],
            "acl_tags": ["public"],
        },
        {
            "id": "pro_bridge",
            "name": "Pro Bridge",
            "description": "External expert handoff protocols, validation, source provenance, and feedback intake.",
            "artifact_types": [
                "pro_boundary",
                "pro_flow",
                "prompt_evidence",
                "feedback_absorption",
                "structured_records",
                "formal_response_completion",
            ],
            "acl_tags": ["public"],
        },
        {
            "id": "governance",
            "name": "Governance",
            "description": "Validation gates, stop rules, output lifecycle, and writeback policy.",
            "artifact_types": ["validation_gates", "pause_gate", "rollback_policy", "output_lifecycle"],
            "acl_tags": ["public"],
        },
        {
            "id": "local_runtime_policy",
            "name": "Local Runtime Policy",
            "description": "Runtime state and local registry rules that require maintainer access.",
            "artifact_types": ["runtime_exclusion"],
            "acl_tags": ["maintainer"],
        },
    ]


def artifact_specs() -> list[dict[str, Any]]:
    return [
        {
            "id": "project.identity",
            "context_id": "meta_project",
            "artifact_type": "project_identity",
            "title": "Project identity and purpose",
            "summary": "Meta_workflow is a meta workflow engine for business workflow design, execution, validation, memory, recall, and evolution.",
            "confidence": 0.98,
            "policy_tags": ["public", "project_truth"],
            "data": {
                "project_name": "Meta_workflow",
                "purpose": "Guide arbitrary projects through business workflow design, execution, validation, memory, recall, and evolution.",
                "target_users": [
                    "project owners with messy goals",
                    "Codex or another coding agent implementing workflows",
                    "external reviewers such as Pro",
                ],
            },
            "citations": [
                CitationSpec("project_name", "README.md", "Meta_workflow is a meta workflow engine workspace."),
                CitationSpec("purpose", "README.md", "Its goal is to guide arbitrary projects through business workflow design, execution, validation, memory, recall, and evolution."),
                CitationSpec("target_users[0]", "docs/architecture/vision.md", "A project owner who needs business workflows designed from messy goals."),
                CitationSpec("target_users[1]", "docs/architecture/vision.md", "Codex or another coding agent implementing and maintaining those workflows."),
                CitationSpec("target_users[2]", "docs/architecture/vision.md", "External reviewers such as Pro who can critique architecture, risks, and plans."),
            ],
        },
        {
            "id": "project.repository_map",
            "context_id": "meta_project",
            "artifact_type": "repository_map",
            "title": "Repository map",
            "summary": "The repository routes contributors through AGENTS, architecture, methodology, Pro handoffs, Pro Bridge, and the MAP source paper.",
            "confidence": 0.95,
            "policy_tags": ["public", "navigation"],
            "data": {
                "repository_map": {
                    "AGENTS.md": "root entry contract and routing rules",
                    "docs/architecture/vision.md": "project direction, target users, engine shape, and roadmap",
                    "docs/methodology/map_methodology.md": "MAP paper methodology adapted for Meta_workflow",
                    "docs/pro_handoffs/first_architecture_review.md": "first Pro architecture review brief",
                    "integrations/pro_bridge/": "guarded external Pro expert integration",
                    "references/papers/s41467-025-63804-5.pdf": "source paper for MAP-style modular planning",
                }
            },
            "citations": [
                CitationSpec("repository_map", "README.md", "## Repository Map"),
                CitationSpec("repository_map.integrations/pro_bridge/", "README.md", "guarded external Pro expert integration"),
                CitationSpec("repository_map.references/papers/s41467-025-63804-5.pdf", "README.md", "source paper for MAP-style modular planning"),
            ],
        },
        {
            "id": "project.hard_boundaries",
            "context_id": "meta_project",
            "artifact_type": "hard_boundaries",
            "title": "Hard boundaries",
            "summary": "Pro is advice, not truth; runtime state and credentials stay out of Git; validation and decision gates cannot be skipped.",
            "confidence": 0.99,
            "policy_tags": ["public", "governance", "external_advice_boundary"],
            "data": {
                "hard_boundaries": [
                    "Pro is external advice, not project truth.",
                    "Pro responses cannot directly change rules, memory, architecture, task status, or acceptance status.",
                    "Runtime registries, local configs, profile ids, nonces, conversation ids, cookies, and tokens must not be committed.",
                    "Prompt validation, response validation, external feedback intake, and local decision gates cannot be skipped.",
                    "Meta_workflow Pro session state must not mix with historical state from other projects.",
                ],
                "external_advice_policy": "Pro feedback becomes project truth only after local verification and local decision gates.",
            },
            "citations": [
                CitationSpec("hard_boundaries[0]", "AGENTS.md", "Pro is external advice, not project truth."),
                CitationSpec("hard_boundaries[1]", "AGENTS.md", "Do not let Pro responses directly change rules, memory, architecture, task status, or acceptance status."),
                CitationSpec("hard_boundaries[2]", "AGENTS.md", "Do not commit `*.local.json`, `*.local.yaml`, runtime registries"),
                CitationSpec("hard_boundaries[3]", "AGENTS.md", "Do not skip prompt validation, response validation, external feedback intake, or local decision gates."),
                CitationSpec("hard_boundaries[4]", "AGENTS.md", "Do not mix Meta_workflow Pro session state with historical state from other projects."),
                CitationSpec("external_advice_policy", "integrations/pro_bridge/protocols/external_feedback_absorption.md", "A Pro statement becomes project truth only after local verification."),
            ],
        },
        {
            "id": "project.decision_placement",
            "context_id": "meta_project",
            "artifact_type": "decision_placement",
            "title": "Decision placement",
            "summary": "Stable architecture, methodology interpretation, Pro review material, and executable Pro behavior have different homes.",
            "confidence": 0.95,
            "policy_tags": ["public", "navigation", "governance"],
            "data": {
                "decision_placement": {
                    "stable_architecture": "docs/architecture/",
                    "research_methodology": "docs/methodology/",
                    "pro_review_briefs_and_outcomes": "docs/pro_handoffs/ or Pro Bridge runtime/intake files",
                    "executable_pro_integration": "integrations/pro_bridge/",
                    "root_contract": "AGENTS.md remains an index and boundary document only",
                }
            },
            "citations": [
                CitationSpec("decision_placement.stable_architecture", "AGENTS.md", "Put stable architecture direction in `docs/architecture/`."),
                CitationSpec("decision_placement.research_methodology", "AGENTS.md", "Put research/methodology interpretation in `docs/methodology/`."),
                CitationSpec("decision_placement.pro_review_briefs_and_outcomes", "AGENTS.md", "Put Pro review briefs and outcomes in `docs/pro_handoffs/` or Pro Bridge runtime/intake files as appropriate."),
                CitationSpec("decision_placement.executable_pro_integration", "AGENTS.md", "Put executable Pro integration behavior in `integrations/pro_bridge/`."),
                CitationSpec("decision_placement.root_contract", "AGENTS.md", "Keep `AGENTS.md` as an index and boundary document only."),
            ],
        },
        {
            "id": "project.local_work_loop",
            "context_id": "meta_project",
            "artifact_type": "work_loop",
            "title": "Local work loop",
            "summary": "Substantial work should understand the goal, inspect state, gather evidence, plan or implement narrowly, validate, and record durable decisions.",
            "confidence": 0.93,
            "policy_tags": ["public", "workflow"],
            "data": {
                "local_work_loop": [
                    "understand the goal",
                    "inspect repo state",
                    "gather evidence",
                    "plan or implement narrowly",
                    "validate",
                    "record durable decisions in the right doc or subsystem",
                ]
            },
            "citations": [
                CitationSpec("local_work_loop", "AGENTS.md", "For substantial work: understand the goal, inspect repo state, gather evidence, plan or implement narrowly, validate, then record any durable decision in the right doc or subsystem."),
            ],
        },
        {
            "id": "architecture.engine_shape",
            "context_id": "architecture",
            "artifact_type": "engine_shape",
            "title": "Engine shape",
            "summary": "Meta_workflow's engine is composed of intake, decomposition, composition, monitoring, prediction, evaluation, orchestration, memory/recall, and external expert bridge subsystems.",
            "confidence": 0.98,
            "policy_tags": ["public", "architecture"],
            "data": {
                "engine_subsystems": [
                    "Intake",
                    "Decomposer",
                    "Composer",
                    "Monitor",
                    "Predictor",
                    "Evaluator",
                    "Orchestrator",
                    "Memory and Recall",
                    "External Expert Bridge",
                ]
            },
            "citations": [
                CitationSpec("engine_subsystems", "docs/architecture/vision.md", "Meta_workflow should evolve into a workflow engine with these subsystems:"),
                CitationSpec("engine_subsystems[0]", "docs/architecture/vision.md", "Intake: capture project goals, constraints, stakeholders, and success criteria."),
                CitationSpec("engine_subsystems[7]", "docs/architecture/vision.md", "Memory and Recall: retrieve prior knowledge and write back verified durable facts."),
                CitationSpec("engine_subsystems[8]", "docs/architecture/vision.md", "External Expert Bridge: request and absorb Pro feedback through controlled protocols."),
            ],
        },
        {
            "id": "architecture.v1_success",
            "context_id": "architecture",
            "artifact_type": "success_criteria",
            "title": "V1 success criteria",
            "summary": "V1 must convert goals into workflow specs, attach validation and acceptance criteria, handle Pro review, separate memory writeback, and resume from state.",
            "confidence": 0.97,
            "policy_tags": ["public", "architecture", "acceptance"],
            "data": {
                "v1_success_criteria": [
                    "A project goal can be converted into a structured workflow spec.",
                    "Every workflow step has owner, evidence, validation, and acceptance criteria.",
                    "External Pro review can be requested through GitHub source refs.",
                    "Memory writeback is explicit and separated from raw conversation.",
                    "The engine can resume from recorded state rather than relying on chat context.",
                ]
            },
            "citations": [
                CitationSpec("v1_success_criteria[0]", "docs/architecture/vision.md", "A project goal can be converted into a structured workflow spec."),
                CitationSpec("v1_success_criteria[1]", "docs/architecture/vision.md", "Every workflow step has owner, evidence, validation, and acceptance criteria."),
                CitationSpec("v1_success_criteria[2]", "docs/architecture/vision.md", "External Pro review can be requested through GitHub source refs."),
                CitationSpec("v1_success_criteria[3]", "docs/architecture/vision.md", "Memory writeback is explicit and separated from raw conversation."),
                CitationSpec("v1_success_criteria[4]", "docs/architecture/vision.md", "The engine can resume from recorded state rather than relying on chat context."),
            ],
        },
        {
            "id": "architecture.roadmap",
            "context_id": "architecture",
            "artifact_type": "roadmap",
            "title": "Architecture roadmap",
            "summary": "The roadmap moves from contracts and Pro Bridge to schemas, runtime, evaluation loops, and later UI/API surfaces.",
            "confidence": 0.96,
            "policy_tags": ["public", "architecture", "roadmap"],
            "data": {
                "roadmap": {
                    "phase_0": "Phase 0: establish repository contracts, Pro Bridge, methodology docs, and source-ref review loop",
                    "phase_1": "Phase 1: define workflow spec schemas, event log, memory records, and recall packets",
                    "phase_2": "Phase 2: build a runnable local engine for planning, gate checks, execution records, and resume",
                    "phase_3": "Phase 3: add evaluation loops, Pro review ingestion, and self-improvement workflows",
                    "phase_4": "Phase 4: add UI/API surfaces after the file and CLI protocol stabilizes",
                }
            },
            "citations": [
                CitationSpec("roadmap.phase_0", "docs/architecture/vision.md", "Phase 0: establish repository contracts, Pro Bridge, methodology docs, and source-ref review loop."),
                CitationSpec("roadmap.phase_1", "docs/architecture/vision.md", "Phase 1: define workflow spec schemas, event log, memory records, and recall packets."),
                CitationSpec("roadmap.phase_2", "docs/architecture/vision.md", "Phase 2: build a runnable local engine for planning, gate checks, execution records, and resume."),
                CitationSpec("roadmap.phase_3", "docs/architecture/vision.md", "Phase 3: add evaluation loops, Pro review ingestion, and self-improvement workflows."),
                CitationSpec("roadmap.phase_4", "docs/architecture/vision.md", "Phase 4: add UI/API surfaces after the file and CLI protocol stabilizes."),
            ],
        },
        {
            "id": "methodology.core",
            "context_id": "methodology",
            "artifact_type": "map_core",
            "title": "MAP core lesson",
            "summary": "The useful idea is functional planning decomposition, not persona-style multi-agent theatrics.",
            "confidence": 0.97,
            "policy_tags": ["public", "methodology"],
            "data": {
                "map_core_lesson": "Factor planning into specialized functions that repeatedly coordinate around a goal, then extend the factorization with durable memory and recall.",
                "avoid": "Do not treat the lesson as simply using many agents.",
            },
            "citations": [
                CitationSpec("map_core_lesson", "docs/methodology/map_methodology.md", "The paper's useful idea is not \"use many agents\"."),
                CitationSpec("map_core_lesson", "docs/methodology/map_methodology.md", "factor planning into specialized functions that repeatedly coordinate around a goal"),
            ],
        },
        {
            "id": "methodology.module_mapping",
            "context_id": "methodology",
            "artifact_type": "map_modules",
            "title": "MAP module mapping",
            "summary": "MAP modules map to Meta_workflow functions: decomposition, action proposal, monitoring, prediction, evaluation, and orchestration.",
            "confidence": 0.96,
            "policy_tags": ["public", "methodology", "architecture"],
            "data": {
                "map_module_mapping": {
                    "TaskDecomposer": "Converts a project/business goal into workflow stages and deliverables.",
                    "Actor": "Proposes workflow steps, tool calls, artifacts, or implementation tasks.",
                    "Monitor": "Enforces policy, scope, evidence, safety, validation, and source-ref gates.",
                    "Predictor": "Simulates likely consequences, dependencies, and downstream state changes.",
                    "Evaluator": "Scores quality, risk, cost, reversibility, and business fit.",
                    "Orchestrator": "Controls workflow lifecycle, pause/resume, retry, escalation, and completion.",
                }
            },
            "citations": [
                CitationSpec("map_module_mapping.TaskDecomposer", "docs/methodology/map_methodology.md", "TaskDecomposer | Turns a high-level goal into subgoals"),
                CitationSpec("map_module_mapping.Actor", "docs/methodology/map_methodology.md", "Actor | Proposes actions for a state and subgoal"),
                CitationSpec("map_module_mapping.Monitor", "docs/methodology/map_methodology.md", "Monitor | Rejects invalid actions and gives feedback"),
                CitationSpec("map_module_mapping.Predictor", "docs/methodology/map_methodology.md", "Predictor | Predicts the next state after an action"),
                CitationSpec("map_module_mapping.Evaluator", "docs/methodology/map_methodology.md", "Evaluator | Scores predicted states against the goal"),
                CitationSpec("map_module_mapping.Orchestrator", "docs/methodology/map_methodology.md", "Orchestrator | Determines subgoal/final-goal completion"),
            ],
        },
        {
            "id": "methodology.extensions",
            "context_id": "methodology",
            "artifact_type": "map_extensions",
            "title": "Meta_workflow extensions beyond MAP",
            "summary": "Meta_workflow adds recall, memory writer, consolidator, external expert bridge, and event log.",
            "confidence": 0.96,
            "policy_tags": ["public", "methodology", "architecture"],
            "data": {
                "meta_workflow_extensions": [
                    "Recall",
                    "Memory Writer",
                    "Consolidator",
                    "External Expert Bridge",
                    "Event Log",
                ]
            },
            "citations": [
                CitationSpec("meta_workflow_extensions[0]", "docs/methodology/map_methodology.md", "Recall: retrieve prior project facts, workflow patterns, decisions, failures, and reusable playbooks."),
                CitationSpec("meta_workflow_extensions[1]", "docs/methodology/map_methodology.md", "Memory Writer: write only verified durable facts, not raw observations or external advice."),
                CitationSpec("meta_workflow_extensions[2]", "docs/methodology/map_methodology.md", "Consolidator: merge repeated lessons into stable project and methodology memory."),
                CitationSpec("meta_workflow_extensions[3]", "docs/methodology/map_methodology.md", "External Expert Bridge: route Pro feedback as evidence, not as authority."),
                CitationSpec("meta_workflow_extensions[4]", "docs/methodology/map_methodology.md", "Event Log: preserve every meaningful state transition for replay and debugging."),
            ],
        },
        {
            "id": "methodology.design_principles",
            "context_id": "methodology",
            "artifact_type": "design_principles",
            "title": "MAP design principles",
            "summary": "The methodology prefers functional modules, gated actions, source-grounded evidence, separate memory writeback, and explicit state.",
            "confidence": 0.95,
            "policy_tags": ["public", "methodology", "governance"],
            "data": {
                "design_principles": [
                    "Prefer functional modules over persona-style agents.",
                    "Gate proposed actions before execution.",
                    "Keep source-grounded evidence attached to every external review.",
                    "Treat memory writeback as a separate decision, not a side effect of conversation.",
                    "Make state explicit.",
                ]
            },
            "citations": [
                CitationSpec("design_principles[0]", "docs/methodology/map_methodology.md", "Prefer functional modules over persona-style agents."),
                CitationSpec("design_principles[1]", "docs/methodology/map_methodology.md", "Gate proposed actions before execution."),
                CitationSpec("design_principles[2]", "docs/methodology/map_methodology.md", "Keep source-grounded evidence attached to every external review."),
                CitationSpec("design_principles[3]", "docs/methodology/map_methodology.md", "Treat memory writeback as a separate decision, not a side effect of conversation."),
                CitationSpec("design_principles[4]", "docs/methodology/map_methodology.md", "Make state explicit: current goal, subgoal, candidate action"),
            ],
        },
        {
            "id": "pro_bridge.boundary",
            "context_id": "pro_bridge",
            "artifact_type": "pro_boundary",
            "title": "Pro Bridge boundary",
            "summary": "Pro is an external expert; its responses must be captured, validated, absorbed, and routed through local gates.",
            "confidence": 0.99,
            "policy_tags": ["public", "external_advice_boundary", "governance"],
            "data": {
                "pro_boundary": [
                    "Pro is an external expert, not the source of truth.",
                    "Pro responses cannot directly change rules, long-term memory, business direction, or acceptance state.",
                    "Every Pro response must be captured, validated, absorbed into a local intake record, and routed through local decision gates.",
                ],
                "external_advice_policy": "trust_policy is always external_advice.",
            },
            "citations": [
                CitationSpec("pro_boundary[0]", "integrations/pro_bridge/README.md", "Pro is an external expert, not the source of truth."),
                CitationSpec("pro_boundary[1]", "integrations/pro_bridge/README.md", "Pro responses cannot directly change rules, long-term memory, business direction, or acceptance state."),
                CitationSpec("pro_boundary[2]", "integrations/pro_bridge/README.md", "Every Pro response must be captured, validated, absorbed into a local intake record, and routed through local decision gates."),
                CitationSpec("external_advice_policy", "integrations/pro_bridge/protocols/external_feedback_absorption.md", "`trust_policy` is always `external_advice`."),
            ],
        },
        {
            "id": "pro_bridge.review_flow",
            "context_id": "pro_bridge",
            "artifact_type": "pro_flow",
            "title": "Pro review flow",
            "summary": "The Pro Bridge flow prepares evidence, validates prompts, reconciles sessions, locks browser targets, captures responses, validates responses, writes intake, and routes decisions.",
            "confidence": 0.95,
            "policy_tags": ["public", "workflow", "governance"],
            "data": {
                "pro_review_flow": [
                    "prepare evidence",
                    "build prompt",
                    "validate-prompt",
                    "project-sessions",
                    "targets/lock",
                    "fill",
                    "manual or guarded send",
                    "watch/capture",
                    "validate-response",
                    "external_feedback_intake",
                    "decision/memory writeback",
                ]
            },
            "citations": [
                CitationSpec("pro_review_flow", "integrations/pro_bridge/README.md", "`prepare evidence -> build prompt -> validate-prompt -> project-sessions -> targets/lock -> fill -> manual or guarded send -> watch/capture -> validate-response -> external_feedback_intake -> decision/memory writeback`"),
                CitationSpec("pro_review_flow", "integrations/pro_bridge/protocols/pro_review_handoff.md", "Route findings through local decision gates before any memory or workflow writeback."),
            ],
        },
        {
            "id": "pro_bridge.prompt_evidence",
            "context_id": "pro_bridge",
            "artifact_type": "prompt_evidence",
            "title": "Required Pro prompt evidence",
            "summary": "Every prompt to Pro must include source repo, source ref, source paths, review goal, expected schema, and local evidence manifest.",
            "confidence": 0.98,
            "policy_tags": ["public", "source_provenance", "governance"],
            "data": {
                "required_prompt_evidence": [
                    "source_repo",
                    "source_ref",
                    "source_paths",
                    "review_goal",
                    "expected_output_schema",
                    "local_evidence_manifest",
                ],
                "source_ref_rule": "If source_ref is unavailable, state the block reason; draft review cannot count as final source-grounded review.",
            },
            "citations": [
                CitationSpec("required_prompt_evidence", "integrations/pro_bridge/README.md", "Each prompt sent to Pro must include `source_repo`, `source_ref`, `source_paths`, `review_goal`, `expected_output_schema`, and `local_evidence_manifest`."),
                CitationSpec("source_ref_rule", "integrations/pro_bridge/protocols/source_ref_provenance.md", "If `source_ref` is not available, the prompt must state the block reason."),
            ],
        },
        {
            "id": "pro_bridge.feedback_absorption",
            "context_id": "pro_bridge",
            "artifact_type": "feedback_absorption",
            "title": "External feedback absorption",
            "summary": "External feedback must preserve raw hashes, validate structure, record confidence and unknowns, split findings, decide adoption, and delay memory writeback.",
            "confidence": 0.96,
            "policy_tags": ["public", "governance", "external_advice_boundary"],
            "data": {
                "feedback_absorption_rules": [
                    "Preserve the raw response path and hash.",
                    "Validate response structure before recording findings.",
                    "Record confidence and remaining unknowns.",
                    "Split advice into P0, P1, or P2 findings.",
                    "Assign each finding an adoption decision.",
                    "Map accepted findings to local workflow work types.",
                    "Write only an intake and ledger entry first; memory writeback requires a later local gate.",
                ]
            },
            "citations": [
                CitationSpec("feedback_absorption_rules[0]", "integrations/pro_bridge/protocols/external_feedback_absorption.md", "Preserve the raw response path and hash."),
                CitationSpec("feedback_absorption_rules[1]", "integrations/pro_bridge/protocols/external_feedback_absorption.md", "Validate response structure before recording findings."),
                CitationSpec("feedback_absorption_rules[6]", "integrations/pro_bridge/protocols/external_feedback_absorption.md", "Write only an intake and ledger entry first; memory writeback requires a later local gate."),
            ],
        },
        {
            "id": "pro_bridge.structured_records",
            "context_id": "pro_bridge",
            "artifact_type": "structured_records",
            "title": "Structured Pro records",
            "summary": "Formal Pro review records use append-only structured ledgers and common audit fields.",
            "confidence": 0.94,
            "policy_tags": ["public", "audit"],
            "data": {
                "runtime_ledgers": [
                    "pro_project_sessions.jsonl",
                    "pro_test_sessions.jsonl",
                    "pro_session_events.jsonl",
                    "pro_review_receipts.jsonl",
                    "external_feedback_ledger.jsonl",
                ],
                "common_record_fields": [
                    "run_id",
                    "source_ref",
                    "pro_session_key",
                    "prompt_path",
                    "prompt_hash",
                    "response_path",
                    "response_hash",
                    "validation_status",
                    "confidence_percent",
                    "adoption_decision",
                    "created_at",
                ],
            },
            "citations": [
                CitationSpec("runtime_ledgers", "integrations/pro_bridge/protocols/structured_records.md", "Runtime ledgers live under `integrations/pro_bridge/runtime/registries/`"),
                CitationSpec("common_record_fields", "integrations/pro_bridge/protocols/structured_records.md", "Every formal Pro review record should include:"),
            ],
        },
        {
            "id": "pro_bridge.formal_completion",
            "context_id": "pro_bridge",
            "artifact_type": "formal_response_completion",
            "title": "Formal Pro response completion",
            "summary": "A formal Pro response must use the response markers, confidence fields, structured findings, and end marker.",
            "confidence": 0.94,
            "policy_tags": ["public", "validation", "external_advice_boundary"],
            "data": {
                "formal_response_completion": {
                    "start_marker": "PRO_RESPONSE:",
                    "end_marker": "PRO_RESPONSE_END",
                    "required_content": [
                        "required confidence fields",
                        "structured findings",
                    ],
                    "non_formal_responses": [
                        "short acknowledgements",
                        "partial thoughts",
                        "draft replies",
                    ],
                }
            },
            "citations": [
                CitationSpec("formal_response_completion.start_marker", "integrations/pro_bridge/protocols/pro_review_handoff.md", "A Pro response is formal only when it contains `PRO_RESPONSE:`"),
                CitationSpec("formal_response_completion.end_marker", "integrations/pro_bridge/protocols/pro_review_handoff.md", "and `PRO_RESPONSE_END`."),
                CitationSpec("formal_response_completion.required_content", "integrations/pro_bridge/protocols/pro_review_handoff.md", "required confidence fields, structured findings"),
                CitationSpec("formal_response_completion.non_formal_responses", "integrations/pro_bridge/protocols/pro_review_handoff.md", "Short acknowledgements, partial thoughts, and draft replies can be saved as evidence but do not count as formal feedback."),
            ],
        },
        {
            "id": "governance.validation_gates",
            "context_id": "governance",
            "artifact_type": "validation_gates",
            "title": "Validation gates",
            "summary": "The Pro workflow gates fill/send, capture acceptance, and memory/workflow writeback separately.",
            "confidence": 0.96,
            "policy_tags": ["public", "validation", "governance"],
            "data": {
                "before_fill_or_send": [
                    "validate-prompt passes",
                    "source_ref is fixed or blocked with a clear reason",
                    "browser window lock is exact and unexpired",
                    "project session reconciliation passes for formal runs",
                ],
                "before_capture_acceptance": [
                    "completion is derived from observable browser state",
                    "captured response is from the locked project conversation",
                    "response path and hash are recorded",
                ],
                "before_memory_or_workflow_writeback": [
                    "validate-response returns schema_valid",
                    "external feedback intake is written",
                    "local decision gate records an adoption decision",
                ],
            },
            "citations": [
                CitationSpec("before_fill_or_send", "integrations/pro_bridge/protocols/validation_gates.md", "## Before fill or send"),
                CitationSpec("before_capture_acceptance", "integrations/pro_bridge/protocols/validation_gates.md", "## Before capture acceptance"),
                CitationSpec("before_memory_or_workflow_writeback", "integrations/pro_bridge/protocols/validation_gates.md", "## Before memory or workflow writeback"),
            ],
        },
        {
            "id": "governance.pause_gate",
            "context_id": "governance",
            "artifact_type": "pause_gate",
            "title": "Single issue pause gate",
            "summary": "A real trust defect pauses the next Pro send until recorded, routed, and resolved or deferred by a local gate.",
            "confidence": 0.95,
            "policy_tags": ["public", "validation", "governance"],
            "data": {
                "pause_triggers": [
                    "browser target lock is ambiguous",
                    "prompt hash does not match the visible input",
                    "response capture is incomplete",
                    "response schema is invalid",
                    "source ref is missing for formal review",
                    "local state and Pro session state disagree",
                    "a memory/rule change would rely only on Pro advice",
                ],
                "resume_rule": "Resume only after the defect is recorded, routed, and the local gate marks it resolved or explicitly deferred.",
            },
            "citations": [
                CitationSpec("pause_triggers", "integrations/pro_bridge/protocols/single_issue_pause_gate.md", "Pause triggers:"),
                CitationSpec("resume_rule", "integrations/pro_bridge/protocols/single_issue_pause_gate.md", "Resume only after the defect is recorded, routed, and the local gate marks it resolved or explicitly deferred."),
            ],
        },
        {
            "id": "governance.rollback_policy",
            "context_id": "governance",
            "artifact_type": "rollback_policy",
            "title": "Rollback and stop policy",
            "summary": "When a Pro gate fails, the safe actions are not sending/counting, blocking the run, retaining evidence, and opening a defect record.",
            "confidence": 0.95,
            "policy_tags": ["public", "validation", "governance"],
            "data": {
                "safe_rollback_actions": [
                    "do not send",
                    "do not count the response",
                    "mark the run blocked",
                    "keep raw evidence for diagnosis",
                    "open a follow-up defect record",
                ],
                "unsafe_rollback_actions": [
                    "deleting Pro conversations without an explicit local registry match",
                    "overwriting prompt or response evidence",
                    "converting Pro advice directly into memory",
                    "continuing to a second Pro send while a blocking trust defect is unresolved",
                ],
            },
            "citations": [
                CitationSpec("safe_rollback_actions", "integrations/pro_bridge/protocols/rollback_and_stop.md", "Safe rollback actions:"),
                CitationSpec("unsafe_rollback_actions", "integrations/pro_bridge/protocols/rollback_and_stop.md", "Unsafe rollback actions:"),
            ],
        },
        {
            "id": "governance.output_lifecycle",
            "context_id": "governance",
            "artifact_type": "output_lifecycle",
            "title": "Output lifecycle",
            "summary": "Public outputs are protocols, templates, configs, prompts, and sanitized summaries; runtime outputs stay ignored.",
            "confidence": 0.96,
            "policy_tags": ["public", "runtime_exclusion", "governance"],
            "data": {
                "public_outputs": [
                    "protocols",
                    "templates",
                    "example configs",
                    "source-grounded prompts",
                    "sanitized validation summaries",
                ],
                "runtime_exclusions": [
                    "browser locks",
                    "project session status",
                    "monitor status",
                    "raw Pro responses",
                    "local ledgers",
                    "local configs",
                ],
                "runtime_storage_rule": "Runtime outputs stay under integrations/pro_bridge/runtime/ or *.local.* files and are ignored by git.",
            },
            "citations": [
                CitationSpec("public_outputs", "integrations/pro_bridge/protocols/output_lifecycle.md", "Public outputs:"),
                CitationSpec("runtime_exclusions", "integrations/pro_bridge/protocols/output_lifecycle.md", "Runtime outputs:"),
                CitationSpec("runtime_storage_rule", "integrations/pro_bridge/protocols/output_lifecycle.md", "Runtime outputs stay under `integrations/pro_bridge/runtime/` or `*.local.*` files and are ignored by git."),
            ],
        },
        {
            "id": "runtime.exclusion_rules",
            "context_id": "local_runtime_policy",
            "artifact_type": "runtime_exclusion",
            "title": "Local runtime exclusion rules",
            "summary": "Runtime captures, local configs, browser locks, registries, and raw Pro responses stay out of Git.",
            "confidence": 0.97,
            "policy_tags": ["maintainer", "runtime_exclusion", "governance"],
            "data": {
                "runtime_exclusions": [
                    "*.local.json",
                    "*.local.yaml",
                    "runtime registries",
                    "browser locks",
                    "raw Pro responses",
                    "profile ids",
                    "nonces",
                    "conversation ids",
                    "cookies",
                    "tokens",
                ]
            },
            "citations": [
                CitationSpec("runtime_exclusions", "AGENTS.md", "Do not commit `*.local.json`, `*.local.yaml`, runtime registries, browser locks, raw Pro responses, profile ids, nonces, conversation ids, cookies, or tokens."),
                CitationSpec("runtime_exclusions", "README.md", "Runtime captures, local configs, browser locks, local registries, and Pro responses stay ignored"),
            ],
        },
    ]


def compile_artifacts(conn: sqlite3.Connection) -> dict[str, Any]:
    init_schema(conn)
    source_count = conn.execute("SELECT COUNT(*) AS n FROM sources").fetchone()["n"]
    if source_count == 0:
        ingest_sources(conn)
    now = utc_now()
    with conn:
        conn.execute("DELETE FROM citations")
        conn.execute("DELETE FROM artifacts")
        conn.execute("DELETE FROM contexts")
        for spec in context_specs():
            conn.execute(
                """
                INSERT INTO contexts (id, name, description, artifact_types_json, acl_tags_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    spec["id"],
                    spec["name"],
                    spec["description"],
                    json_dumps(spec["artifact_types"]),
                    json_dumps(spec["acl_tags"]),
                    now,
                ),
            )

        for spec in artifact_specs():
            source_hashes: dict[str, str] = {}
            for citation in spec["citations"]:
                source = get_source(conn, citation.source_path)
                source_hashes[citation.source_path] = source["content_hash"]
            conn.execute(
                """
                INSERT INTO artifacts
                  (id, context_id, artifact_type, title, summary, data_json, confidence,
                   policy_tags_json, source_hashes_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    spec["id"],
                    spec["context_id"],
                    spec["artifact_type"],
                    spec["title"],
                    spec["summary"],
                    json_dumps(spec["data"]),
                    spec["confidence"],
                    json_dumps(spec["policy_tags"]),
                    json_dumps(source_hashes),
                    now,
                ),
            )
            for citation in spec["citations"]:
                source = get_source(conn, citation.source_path)
                start, end, quote = find_line_range(source["content"], citation.needle)
                conn.execute(
                    """
                    INSERT INTO citations
                      (id, artifact_id, field_path, source_id, path, line_start, line_end, quote, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        stable_id(spec["id"], citation.field_path, citation.source_path, citation.needle, length=24),
                        spec["id"],
                        citation.field_path,
                        source["id"],
                        citation.source_path,
                        start,
                        end,
                        quote or citation.needle,
                        citation.confidence,
                    ),
                )
    return {
        "status": "compiled",
        "context_count": len(context_specs()),
        "artifact_count": len(artifact_specs()),
        "citation_count": conn.execute("SELECT COUNT(*) AS n FROM citations").fetchone()["n"],
    }


def validate_query(query: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(query, dict):
        return ["query must be a JSON object"]
    if not isinstance(query.get("ask"), str) or not query.get("ask", "").strip():
        errors.append("ask must be a non-empty string")
    if "contexts" in query and not isinstance(query["contexts"], list):
        errors.append("contexts must be a list when present")
    if "where" in query and not isinstance(query["where"], dict):
        errors.append("where must be an object when present")
    if "shape" in query:
        shape = query["shape"]
        if not isinstance(shape, dict) or shape.get("type") not in {None, "object"}:
            errors.append("shape must be an object schema")
        if isinstance(shape, dict) and "properties" in shape and not isinstance(shape["properties"], dict):
            errors.append("shape.properties must be an object when present")
    if "confidence" in query and not isinstance(query["confidence"], (dict, int, float)):
        errors.append("confidence must be an object or number when present")
    if "budget" in query and not isinstance(query["budget"], dict):
        errors.append("budget must be an object when present")
    return errors


def confidence_min(query: dict[str, Any]) -> float:
    value = query.get("confidence", {})
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        return float(value.get("min", 0.0))
    return 0.0


def budget_max_artifacts(query: dict[str, Any]) -> int:
    budget = query.get("budget") if isinstance(query.get("budget"), dict) else {}
    if "max_artifacts" in budget:
        return max(1, int(budget["max_artifacts"]))
    depth = budget.get("depth", "standard")
    return {"quick": 3, "standard": 6, "deep": 12}.get(depth, 6)


def load_contexts(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    return {row["id"]: row for row in conn.execute("SELECT * FROM contexts")}


def artifact_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM artifacts"))


def row_json(row: sqlite3.Row, key: str, default: Any) -> Any:
    return json_loads(row[key], default)


def artifact_search_text(row: sqlite3.Row) -> str:
    return " ".join(
        [
            row["id"],
            row["context_id"],
            row["artifact_type"],
            row["title"],
            row["summary"],
            row["data_json"],
            row["policy_tags_json"],
        ]
    )


def score_text(query_tokens: list[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    hay = Counter(tokenize(text))
    score = 0.0
    for token in query_tokens:
        if token in hay:
            score += 2.0 + math.log1p(hay[token])
        else:
            for key in hay:
                if token in key or key in token:
                    score += 0.35
                    break
    return score


def citation_rows(conn: sqlite3.Connection, artifact_id: str, field_prefix: str | None = None) -> list[dict[str, Any]]:
    if field_prefix:
        rows = conn.execute(
            """
            SELECT field_path, path, line_start, line_end, quote, confidence
            FROM citations
            WHERE artifact_id = ?
              AND (field_path = ? OR field_path LIKE ?)
            ORDER BY field_path, path, line_start
            """,
            (artifact_id, field_prefix, f"{field_prefix}[%"),
        ).fetchall()
        if not rows:
            rows = conn.execute(
                """
                SELECT field_path, path, line_start, line_end, quote, confidence
                FROM citations
                WHERE artifact_id = ? AND field_path LIKE ?
                ORDER BY field_path, path, line_start
                """,
                (artifact_id, f"{field_prefix}.%"),
            ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT field_path, path, line_start, line_end, quote, confidence
            FROM citations
            WHERE artifact_id = ?
            ORDER BY field_path, path, line_start
            """,
            (artifact_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def check_stale_artifact(conn: sqlite3.Connection, row: sqlite3.Row) -> bool:
    hashes = row_json(row, "source_hashes_json", {})
    for path, expected_hash in hashes.items():
        source = conn.execute("SELECT content_hash FROM sources WHERE path = ?", (path,)).fetchone()
        if source is None or source["content_hash"] != expected_hash:
            return True
    return False


def select_artifacts(conn: sqlite3.Connection, query: dict[str, Any]) -> tuple[list[sqlite3.Row], list[str], bool]:
    contexts = load_contexts(conn)
    requested_contexts = query.get("contexts") or list(contexts.keys())
    requested_contexts = [str(item) for item in requested_contexts]
    where = query.get("where") if isinstance(query.get("where"), dict) else {}
    principal_tags = set(where.get("principal_tags") or ["public"])
    allowed_contexts: set[str] = set()
    warnings: list[str] = []
    filtered_by_acl = False

    for context_id in requested_contexts:
        context = contexts.get(context_id)
        if context is None:
            warnings.append(f"unknown_context:{context_id}")
            continue
        required = set(row_json(context, "acl_tags_json", []))
        if not required.issubset(principal_tags):
            filtered_by_acl = True
            warnings.append(f"context_acl_filtered:{context_id}")
            continue
        allowed_contexts.add(context_id)

    artifact_types = set(where.get("artifact_types") or [])
    if "artifact_type" in where:
        artifact_types.add(str(where["artifact_type"]))
    tags_any = set(where.get("policy_tags_any") or [])
    tags_all = set(where.get("policy_tags_all") or [])
    exclude_tags = set(where.get("exclude_policy_tags") or [])
    min_conf = confidence_min(query)

    ask_text = query.get("ask", "")
    shape_props = " ".join((query.get("shape") or {}).get("properties", {}).keys())
    query_tokens = tokenize(f"{ask_text} {shape_props}")
    candidates = []
    for row in artifact_rows(conn):
        if row["context_id"] not in allowed_contexts:
            continue
        if row["confidence"] < min_conf:
            continue
        if artifact_types and row["artifact_type"] not in artifact_types:
            continue
        policy_tags = set(row_json(row, "policy_tags_json", []))
        if tags_any and not policy_tags.intersection(tags_any):
            continue
        if tags_all and not tags_all.issubset(policy_tags):
            continue
        if exclude_tags and policy_tags.intersection(exclude_tags):
            continue
        score = score_text(query_tokens, artifact_search_text(row))
        if score > 0 or not query_tokens:
            candidates.append((score, row))

    candidates.sort(key=lambda item: (item[0], item[1]["confidence"], item[1]["id"]), reverse=True)
    selected = [row for _, row in candidates[: budget_max_artifacts(query)]]
    for row in selected:
        if check_stale_artifact(conn, row):
            warnings.append(f"stale_artifact:{row['id']}")
    return selected, warnings, filtered_by_acl


def field_score(prop: str, ask: str, path: str, value: Any, artifact: sqlite3.Row) -> float:
    exact = 30.0 if prop == path or path.endswith(f".{prop}") else 0.0
    prop_tokens = tokenize(prop.replace("_", " "))
    ask_tokens = tokenize(ask)
    text = f"{path} {value} {artifact['title']} {artifact['summary']}"
    return exact + score_text(prop_tokens, text) * 1.8 + score_text(ask_tokens, text) * 0.15 + artifact["confidence"]


def best_field(conn: sqlite3.Connection, prop: str, query: dict[str, Any], artifacts: list[sqlite3.Row]) -> dict[str, Any] | None:
    best: tuple[float, sqlite3.Row, str, Any] | None = None
    for artifact in artifacts:
        data = row_json(artifact, "data_json", {})
        for path, value in flatten_json(data):
            if not path:
                continue
            score = field_score(prop, query.get("ask", ""), path, value, artifact)
            if best is None or score > best[0]:
                best = (score, artifact, path, value)
    if best is None:
        return None
    _, artifact, path, value = best
    citations = citation_rows(conn, artifact["id"], path)
    if not citations and "." in path:
        citations = citation_rows(conn, artifact["id"], path.split(".")[0])
    return {
        "value": value,
        "source_artifact": artifact["id"],
        "field_path": path,
        "confidence": artifact["confidence"],
        "citations": citations,
    }


def run_compiled_query(conn: sqlite3.Connection, query: dict[str, Any]) -> dict[str, Any]:
    init_schema(conn)
    errors = validate_query(query)
    if errors:
        raise KnowledgeError("; ".join(errors))

    start = time.perf_counter()
    artifacts, warnings, filtered_by_acl = select_artifacts(conn, query)
    shape = query.get("shape") if isinstance(query.get("shape"), dict) else {}
    props = shape.get("properties") if isinstance(shape.get("properties"), dict) else {}
    fields: dict[str, Any] = {}
    answer: dict[str, Any] = {}
    all_citations: list[dict[str, Any]] = []

    if props:
        for prop in props:
            found = best_field(conn, prop, query, artifacts)
            if found is None:
                fields[prop] = {
                    "value": None,
                    "source_artifact": None,
                    "field_path": None,
                    "confidence": 0.0,
                    "citations": [],
                }
                answer[prop] = None
                warnings.append(f"field_unresolved:{prop}")
                continue
            fields[prop] = found
            answer[prop] = found["value"]
            all_citations.extend(found["citations"])
    else:
        answer["artifacts"] = [
            {
                "id": row["id"],
                "context_id": row["context_id"],
                "artifact_type": row["artifact_type"],
                "title": row["title"],
                "summary": row["summary"],
                "data": row_json(row, "data_json", {}),
            }
            for row in artifacts
        ]
        for row in artifacts:
            all_citations.extend(citation_rows(conn, row["id"]))

    if query.get("ground", False) and props:
        for prop, field in fields.items():
            if not field["citations"]:
                warnings.append(f"missing_citation:{prop}")

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    citation_keys = set()
    deduped_citations = []
    for citation in all_citations:
        key = (citation["path"], citation["line_start"], citation["field_path"], citation["quote"])
        if key not in citation_keys:
            citation_keys.add(key)
            deduped_citations.append(citation)

    confidences = [row["confidence"] for row in artifacts]
    served_payload = {"answer": answer, "citations": deduped_citations}
    source_bytes = len(json_dumps(served_payload).encode("utf-8"))
    return {
        "answer": answer,
        "fields": fields,
        "citations": deduped_citations,
        "confidence": {
            "aggregate": round(min(confidences), 3) if confidences else 0.0,
            "selected_artifact_count": len(artifacts),
        },
        "budget_used": {
            "latency_ms": round(elapsed_ms, 3),
            "depth": (query.get("budget") or {}).get("depth", "standard") if isinstance(query.get("budget"), dict) else "standard",
            "artifacts": len(artifacts),
            "source_bytes_proxy": source_bytes,
            "steps": 1,
        },
        "filtered_by_acl": filtered_by_acl,
        "warnings": warnings,
    }


def escape_fts_query(tokens: list[str]) -> str:
    clean = []
    for token in tokens[:10]:
        normalized = re.sub(r"[^A-Za-z0-9_./:-]", "", token)
        if normalized:
            clean.append(f'"{normalized}"')
    return " OR ".join(clean) or '"meta_workflow"'


def run_baseline_query(conn: sqlite3.Connection, query: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    terms = tokenize(query.get("ask", "") + " " + " ".join((query.get("shape") or {}).get("properties", {}).keys()))
    fts_query = escape_fts_query(terms)
    rows: list[sqlite3.Row] = []
    try:
        rows = list(
            conn.execute(
                """
                SELECT s.path, s.content, s.byte_count,
                       snippet(source_fts, 2, '[', ']', ' ... ', 24) AS snippet
                FROM source_fts
                JOIN sources s ON s.id = source_fts.source_id
                WHERE source_fts MATCH ?
                LIMIT 6
                """,
                (fts_query,),
            )
        )
    except sqlite3.OperationalError:
        for source in conn.execute("SELECT path, content, byte_count FROM sources LIMIT 20"):
            if any(term in source["content"].lower() for term in terms):
                rows.append(source)
            if len(rows) >= 6:
                break

    snippets = []
    for row in rows:
        snippet = row["snippet"] if "snippet" in row.keys() and row["snippet"] else row["content"][:800]
        snippets.append({"path": row["path"], "snippet": snippet})

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    source_bytes = sum(int(row["byte_count"]) for row in rows)
    return {
        "answer": {"snippets": snippets},
        "fields": {},
        "citations": [],
        "confidence": {"aggregate": 0.0, "selected_artifact_count": 0},
        "budget_used": {
            "latency_ms": round(elapsed_ms, 3),
            "depth": "baseline",
            "artifacts": 0,
            "source_bytes_proxy": source_bytes,
            "steps": max(1, len(rows)),
        },
        "filtered_by_acl": False,
        "warnings": ["baseline_returns_raw_sources_not_typed_artifacts"],
    }


def sec_available_artifacts(conn: sqlite3.Connection, corpus: str) -> list[sqlite3.Row]:
    rows = list(
        conn.execute(
            """
            SELECT a.*
            FROM sec_artifacts a
            JOIN sec_filings f ON f.id = a.filing_id
            WHERE a.corpus = ?
            ORDER BY a.ticker, f.filing_date DESC, f.report_date DESC
            """,
            (corpus,),
        )
    )
    latest: list[sqlite3.Row] = []
    seen: set[str] = set()
    for row in rows:
        if row["ticker"] in seen:
            continue
        seen.add(row["ticker"])
        latest.append(row)
    return latest


def sec_artifact_by_ticker(conn: sqlite3.Connection, corpus: str, ticker: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT a.*
        FROM sec_artifacts a
        JOIN sec_filings f ON f.id = a.filing_id
        WHERE a.corpus = ? AND a.ticker = ?
        ORDER BY f.filing_date DESC, f.report_date DESC
        LIMIT 1
        """,
        (corpus, ticker.upper()),
    ).fetchone()


def sec_query_tickers(conn: sqlite3.Connection, corpus: str, query: dict[str, Any]) -> list[str]:
    where = query.get("where") if isinstance(query.get("where"), dict) else {}
    requested = [str(ticker).upper() for ticker in where.get("tickers", []) if str(ticker).strip()]
    if requested:
        return requested
    known = [row["ticker"] for row in conn.execute("SELECT DISTINCT ticker FROM sec_artifacts WHERE corpus = ?", (corpus,))]
    ask = query.get("ask", "").upper()
    return [ticker for ticker in known if re.search(rf"\b{re.escape(ticker)}\b", ask)]


def sec_query_fields(query: dict[str, Any]) -> list[str]:
    if isinstance(query.get("sec_fields"), list):
        return [str(field) for field in query["sec_fields"]]
    props = (query.get("shape") or {}).get("properties", {}) if isinstance(query.get("shape"), dict) else {}
    fields = [field for field in props if field in SEC_FIELD_LABELS]
    return fields or ["revenue_usd", "net_income_usd", "employees", "risk_factor_summary"]


def sec_make_company_answer(artifact: sqlite3.Row, fields: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = row_json(artifact, "data_json", {})
    citations = row_json(artifact, "citations_json", {})
    company = {
        "ticker": artifact["ticker"],
        "company": artifact["company"],
        "fiscal_year": data.get("fiscal_year"),
    }
    used_citations: list[dict[str, Any]] = []
    for field in fields:
        if field == "capex_to_revenue_ratio":
            capex = data.get("capex_usd")
            revenue = data.get("revenue_usd")
            company[field] = round(float(capex) / float(revenue), 6) if capex and revenue else None
            used_citations.extend(citations.get("capex_usd", []))
            used_citations.extend(citations.get("revenue_usd", []))
            continue
        if field == "net_income_margin":
            net_income = data.get("net_income_usd")
            revenue = data.get("revenue_usd")
            company[field] = round(float(net_income) / float(revenue), 6) if net_income and revenue else None
            used_citations.extend(citations.get("net_income_usd", []))
            used_citations.extend(citations.get("revenue_usd", []))
            continue
        if field == "revenue_to_assets_ratio":
            revenue = data.get("revenue_usd")
            assets = data.get("assets_usd")
            company[field] = round(float(revenue) / float(assets), 6) if revenue and assets else None
            used_citations.extend(citations.get("revenue_usd", []))
            used_citations.extend(citations.get("assets_usd", []))
            continue
        company[field] = data.get(field)
        used_citations.extend(citations.get(field, []))
    return company, used_citations


def run_sec_compiled_query(conn: sqlite3.Connection, query: dict[str, Any], corpus: str = SEC_CORPUS_ID) -> dict[str, Any]:
    start = time.perf_counter()
    tickers = sec_query_tickers(conn, corpus, query)
    fields = sec_query_fields(query)
    warnings: list[str] = []
    companies = []
    citations: list[dict[str, Any]] = []
    for ticker in tickers:
        artifact = sec_artifact_by_ticker(conn, corpus, ticker)
        if artifact is None:
            warnings.append(f"missing_sec_artifact:{ticker}")
            continue
        company, used = sec_make_company_answer(artifact, fields)
        companies.append(company)
        citations.extend(used)

    deduped = []
    seen = set()
    for citation in citations:
        key = (citation.get("kind"), citation.get("path"), citation.get("line_start"), citation.get("quote"), citation.get("tag"))
        if key not in seen:
            seen.add(key)
            deduped.append(citation)
    source_bytes = len(json_dumps({"companies": companies, "citations": deduped}).encode("utf-8"))
    latency_ms = (time.perf_counter() - start) * 1000.0
    return {
        "answer": {"companies": companies},
        "fields": {
            "companies": {
                "value": companies,
                "source_artifact": "sec.company_fact_sheet",
                "field_path": "companies",
                "confidence": 0.9 if companies else 0.0,
                "citations": deduped,
            }
        },
        "citations": deduped,
        "confidence": {"aggregate": 0.9 if companies else 0.0, "selected_artifact_count": len(companies)},
        "budget_used": {
            "latency_ms": round(latency_ms, 3),
            "depth": "compiled",
            "artifacts": len(companies),
            "source_bytes_proxy": source_bytes,
            "steps": 1 if companies else 0,
        },
        "filtered_by_acl": False,
        "warnings": warnings,
    }


def sec_search_terms(query: dict[str, Any]) -> list[str]:
    field_terms = [SEC_FIELD_LABELS.get(field, field) for field in sec_query_fields(query)]
    return tokenize(query.get("ask", "") + " " + " ".join(field_terms))


def run_sec_coding_sandbox_query(conn: sqlite3.Connection, query: dict[str, Any], corpus: str = SEC_CORPUS_ID) -> dict[str, Any]:
    start = time.perf_counter()
    tickers = sec_query_tickers(conn, corpus, query)
    terms = sec_search_terms(query)
    snippets = []
    source_bytes = 0
    steps = 0
    for ticker in tickers:
        filing = conn.execute("SELECT * FROM sec_filings WHERE corpus = ? AND ticker = ?", (corpus, ticker)).fetchone()
        if filing is None:
            continue
        text = read_text(ROOT_DIR / filing["local_text_path"])
        source_bytes += len(text.encode("utf-8"))
        steps += 1
        lowered = text.lower()
        for term in terms[:12]:
            index = lowered.find(term.lower())
            steps += 1
            if index >= 0:
                snippet = text[max(0, index - 350) : min(len(text), index + 650)]
                snippets.append({"ticker": ticker, "path": filing["local_text_path"], "snippet": re.sub(r"\s+", " ", snippet).strip()})
                if len(snippets) >= 20:
                    break
    latency_ms = (time.perf_counter() - start) * 1000.0
    return {
        "answer": {"snippets": snippets},
        "fields": {},
        "citations": [],
        "confidence": {"aggregate": 0.0, "selected_artifact_count": 0},
        "budget_used": {
            "latency_ms": round(latency_ms, 3),
            "depth": "coding_sandbox",
            "artifacts": 0,
            "source_bytes_proxy": source_bytes,
            "steps": max(1, steps),
        },
        "filtered_by_acl": False,
        "warnings": ["coding_sandbox_simulates_file_search_and_read_loops"],
    }


def run_sec_agentic_rag_query(conn: sqlite3.Connection, query: dict[str, Any], corpus: str = SEC_CORPUS_ID) -> dict[str, Any]:
    start = time.perf_counter()
    tickers = sec_query_tickers(conn, corpus, query)
    terms = sec_search_terms(query)
    expansions = []
    if tickers:
        expansions.append(" OR ".join(f'"{ticker}"' for ticker in tickers))
    field_query = " OR ".join(f'"{term}"' for term in terms[:10])
    if field_query:
        expansions.append(field_query)
    if tickers and field_query:
        expansions.append("(" + " OR ".join(f'"{ticker}"' for ticker in tickers) + ") " + field_query)
    if not expansions:
        expansions.append('"10-K"')

    scored: dict[str, tuple[float, sqlite3.Row]] = {}
    for ranker, fts_query in enumerate(expansions):
        try:
            rows = list(
                conn.execute(
                    """
                    SELECT c.*, snippet(sec_chunk_fts, 4, '[', ']', ' ... ', 32) AS snippet
                    FROM sec_chunk_fts
                    JOIN sec_chunks c ON c.id = sec_chunk_fts.chunk_id
                    WHERE sec_chunk_fts MATCH ? AND c.corpus = ?
                    LIMIT 18
                    """,
                    (fts_query, corpus),
                )
            )
        except sqlite3.OperationalError:
            rows = []
        for rank, row in enumerate(rows, start=1):
            current = scored.get(row["id"], (0.0, row))[0]
            scored[row["id"]] = (current + 1.0 / (rank + 60 + ranker), row)
    selected = [row for _, row in sorted(scored.values(), key=lambda item: item[0], reverse=True)[:24]]
    snippets = []
    source_bytes = 0
    for row in selected:
        snippet = row["snippet"] if "snippet" in row.keys() and row["snippet"] else row["text"][:900]
        source_bytes += int(row["byte_count"])
        snippets.append(
            {
                "ticker": row["ticker"],
                "company": row["company"],
                "line_start": row["line_start"],
                "line_end": row["line_end"],
                "snippet": re.sub(r"\s+", " ", snippet).strip(),
            }
        )
    latency_ms = (time.perf_counter() - start) * 1000.0
    return {
        "answer": {"snippets": snippets},
        "fields": {},
        "citations": [],
        "confidence": {"aggregate": 0.0, "selected_artifact_count": 0},
        "budget_used": {
            "latency_ms": round(latency_ms, 3),
            "depth": "agentic_rag",
            "artifacts": 0,
            "source_bytes_proxy": source_bytes,
            "steps": max(1, len(expansions) + len(selected)),
        },
        "filtered_by_acl": False,
        "warnings": ["agentic_rag_returns_ranked_chunks_not_typed_artifacts"],
    }


def sec_eval_query(question: str, tickers: list[str], fields: list[str], category: str, corpus: str = SEC_CORPUS_ID) -> dict[str, Any]:
    return {
        "ask": question,
        "contexts": [corpus],
        "where": {"principal_tags": ["public"], "tickers": tickers},
        "ground": True,
        "shape": {"type": "object", "properties": {"companies": {"type": "array"}}},
        "sec_fields": fields,
        "confidence": {"min": 0.6},
        "budget": {"depth": "standard", "latency_ms": 120000, "category": category},
    }


def sec_non_null_fields(data: dict[str, Any], candidates: list[str]) -> list[str]:
    return [field for field in candidates if data.get(field) not in (None, "", [])]


def balanced_case_limit(cases: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if limit >= 150:
        return cases[:limit]
    balanced: list[dict[str, Any]] = []
    grouped = {category: [case for case in cases if case["category"] == category] for category in ["multi_fact", "multi_company", "multi_step"]}
    while len(balanced) < limit and any(grouped.values()):
        for category in ["multi_fact", "multi_company", "multi_step"]:
            if grouped[category] and len(balanced) < limit:
                balanced.append(grouped[category].pop(0))
    return balanced


def sec_eval_case_specs(conn: sqlite3.Connection, corpus: str = SEC_CORPUS_ID, limit: int = 150) -> list[dict[str, Any]]:
    artifacts = sec_available_artifacts(conn, corpus)
    parsed = [(row, row_json(row, "data_json", {})) for row in artifacts]
    cases: list[dict[str, Any]] = []
    metric_fields = [
        "revenue_usd",
        "net_income_usd",
        "assets_usd",
        "capex_usd",
        "r_and_d_usd",
        "share_repurchases_usd",
        "operating_cash_flow_usd",
        "employees",
    ]
    fact_fields = metric_fields + ["risk_factor_summary", "segments", "acquisitions"]

    for row, data in parsed:
        fields = sec_non_null_fields(data, fact_fields)[:4]
        if len(fields) < 2:
            continue
        fiscal_year = data.get("fiscal_year") or "reported"
        question = f"For {row['ticker']}'s {fiscal_year} 10-K, return " + ", ".join(SEC_FIELD_LABELS.get(field, field) for field in fields) + "."
        contains = [row["ticker"]]
        for field in fields:
            if field in metric_fields and data.get(field) not in (None, ""):
                contains.append(str(data[field]))
            if len(contains) >= 3:
                break
        cases.append(
            {
                "id": f"sec_mf_{len(cases)+1:03d}",
                "suite": SEC_SUITE_NAME,
                "category": "multi_fact",
                "question": question,
                "query": sec_eval_query(question, [row["ticker"]], fields, "multi_fact", corpus),
                "expected": {"contains": contains, "required_fields": ["companies"], "grounded": True},
            }
        )
        if sum(1 for case in cases if case["category"] == "multi_fact") >= 50:
            break

    comparable = [(row, data) for row, data in parsed if data.get("revenue_usd") not in (None, "") and data.get("net_income_usd") not in (None, "")]
    compare_fields = ["revenue_usd", "net_income_usd"]
    if len(comparable) < 30:
        comparable = [(row, data) for row, data in parsed if data.get("revenue_usd") not in (None, "") and data.get("assets_usd") not in (None, "")]
        compare_fields = ["revenue_usd", "assets_usd"]
    if len(comparable) < 30:
        comparable = [(row, data) for row, data in parsed if len(sec_non_null_fields(data, metric_fields)) >= 2]
        compare_fields = sec_non_null_fields(comparable[0][1], metric_fields)[:2] if comparable else ["revenue_usd", "net_income_usd"]
    for index in range(0, min(len(comparable) - 2, 150), 3):
        trio = comparable[index : index + 3]
        tickers = [row["ticker"] for row, _ in trio]
        years = [str(data.get("fiscal_year") or "reported") for _, data in trio]
        question = (
            f"Compare {SEC_FIELD_LABELS.get(compare_fields[0], compare_fields[0])} and "
            f"{SEC_FIELD_LABELS.get(compare_fields[1], compare_fields[1])} for "
            f"{', '.join(f'{ticker} ({year})' for ticker, year in zip(tickers, years))}."
        )
        cases.append(
            {
                "id": f"sec_mc_{len([c for c in cases if c['category']=='multi_company'])+1:03d}",
                "suite": SEC_SUITE_NAME,
                "category": "multi_company",
                "question": question,
                "query": sec_eval_query(question, tickers, compare_fields, "multi_company", corpus),
                "expected": {"contains": tickers, "required_fields": ["companies"], "grounded": True},
            }
        )
        if sum(1 for case in cases if case["category"] == "multi_company") >= 50:
            break

    derived_specs = [
        ("capex_usd", "revenue_usd", "capex_to_revenue_ratio", "capex as a share of revenue"),
        ("net_income_usd", "revenue_usd", "net_income_margin", "net income margin"),
        ("revenue_usd", "assets_usd", "revenue_to_assets_ratio", "revenue as a share of assets"),
    ]
    derived_rows: list[tuple[sqlite3.Row, dict[str, Any], str, str, str, str]] = []
    seen_derived: set[str] = set()
    for numerator, denominator, ratio_field, label in derived_specs:
        for row, data in parsed:
            if row["ticker"] in seen_derived:
                continue
            if data.get(numerator) in (None, "") or data.get(denominator) in (None, ""):
                continue
            seen_derived.add(row["ticker"])
            derived_rows.append((row, data, numerator, denominator, ratio_field, label))
            if len(derived_rows) >= 50:
                break
        if len(derived_rows) >= 50:
            break
    for row, data, numerator, denominator, ratio_field, label in derived_rows[:50]:
        fiscal_year = data.get("fiscal_year") or "reported"
        question = f"For {row['ticker']}, derive {label} from {fiscal_year} 10-K facts and return the source fields."
        cases.append(
            {
                "id": f"sec_ms_{len([c for c in cases if c['category']=='multi_step'])+1:03d}",
                "suite": SEC_SUITE_NAME,
                "category": "multi_step",
                "question": question,
                "query": sec_eval_query(question, [row["ticker"]], [denominator, numerator, ratio_field], "multi_step", corpus),
                "expected": {"contains": [row["ticker"], str(data[denominator]), str(data[numerator])], "required_fields": ["companies"], "grounded": True},
            }
        )

    return balanced_case_limit(cases, limit)


def seed_case_specs(conn: sqlite3.Connection, suite: str, cases: list[dict[str, Any]], limit: int = 150) -> dict[str, Any]:
    if not cases:
        raise KnowledgeError(f"No eval cases could be generated for suite {suite}.")
    now = utc_now()
    with conn:
        for case in cases[:limit]:
            conn.execute(
                """
                INSERT INTO eval_cases (id, suite, category, question, query_json, expected_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  suite = excluded.suite,
                  category = excluded.category,
                  question = excluded.question,
                  query_json = excluded.query_json,
                  expected_json = excluded.expected_json,
                  created_at = excluded.created_at
                """,
                (case["id"], suite, case["category"], case["question"], json_dumps(case["query"]), json_dumps(case["expected"]), now),
            )
    return {"status": "seeded", "suite": suite, "case_count": min(len(cases), limit)}


def seed_sec_eval_cases(conn: sqlite3.Connection, corpus: str, limit: int = 150) -> dict[str, Any]:
    return seed_case_specs(conn, SEC_SUITE_NAME, sec_eval_case_specs(conn, corpus, limit), limit)


def seed_kraft_eval_cases_from_locked(conn: sqlite3.Connection, corpus: str, suite: str, limit: int = 150) -> dict[str, Any]:
    rows = read_jsonl(sec_paths(corpus)["groundtruth"])
    if not rows:
        raise KnowledgeError(f"Locked ground truth missing for {suite}. Run sec-groundtruth-build first.")
    cases = []
    for row in rows[:limit]:
        cases.append(
            {
                "id": row["case_id"],
                "suite": suite,
                "category": row["category"],
                "question": row["question"],
                "query": row["query"],
                "expected": row["expected"],
            }
        )
    return seed_case_specs(conn, suite, cases, limit)


def latest_sec_filings(conn: sqlite3.Connection, corpus: str) -> list[sqlite3.Row]:
    rows = list(
        conn.execute(
            """
            SELECT *
            FROM sec_filings
            WHERE corpus = ?
            ORDER BY ticker, filing_date DESC, report_date DESC
            """,
            (corpus,),
        )
    )
    latest = []
    seen: set[str] = set()
    for row in rows:
        if row["ticker"] in seen:
            continue
        seen.add(row["ticker"])
        latest.append(row)
    return latest


def ground_truth_from_filing(conn: sqlite3.Connection, filing: sqlite3.Row) -> dict[str, Any]:
    artifact_like = extract_company_artifact(conn, filing)
    data = artifact_like["data"]
    citations = artifact_like["citations"]
    metadata = row_json(filing, "metadata_json", {})
    return {
        "filing_id": filing["id"],
        "ticker": filing["ticker"],
        "company": filing["company"],
        "sector": metadata.get("sector", ""),
        "fiscal_year": data.get("fiscal_year") or filing["fiscal_year"],
        "data": data,
        "citations": citations,
        "source_pipeline": "independent_companyfacts_xbrl_then_filing_text",
    }


def flatten_citations_for_fields(citations: dict[str, list[dict[str, Any]]], fields: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen = set()
    for field in fields:
        for citation in citations.get(field, []):
            key = (field, citation.get("path"), citation.get("line_start"), citation.get("quote"), citation.get("tag"))
            if key in seen:
                continue
            seen.add(key)
            rows.append({"field": field, **citation})
    return rows


def sec_groundtruth_case_specs(conn: sqlite3.Connection, corpus: str, suite: str, limit: int = 150) -> list[dict[str, Any]]:
    records = [ground_truth_from_filing(conn, filing) for filing in latest_sec_filings(conn, corpus)]
    metric_fields = [
        "revenue_usd",
        "net_income_usd",
        "assets_usd",
        "capex_usd",
        "r_and_d_usd",
        "share_repurchases_usd",
        "operating_cash_flow_usd",
        "employees",
    ]
    fact_fields = metric_fields + ["risk_factor_summary", "segments", "acquisitions"]
    cases: list[dict[str, Any]] = []

    for record in records:
        data = record["data"]
        fields = sec_non_null_fields(data, fact_fields)[:4]
        if len(fields) < 2:
            continue
        contains = [record["ticker"]]
        for field in fields:
            if field in metric_fields and data.get(field) not in (None, ""):
                contains.append(str(data[field]))
            if len(contains) >= 3:
                break
        question = f"For {record['ticker']}'s {record['fiscal_year']} 10-K, return " + ", ".join(SEC_FIELD_LABELS.get(field, field) for field in fields) + "."
        case_id = f"kraft_mf_{sum(1 for case in cases if case['category'] == 'multi_fact') + 1:03d}"
        cases.append(
            {
                "case_id": case_id,
                "suite": suite,
                "category": "multi_fact",
                "difficulty": "hard_public_replication",
                "topic": "single_company_multi_fact",
                "question": question,
                "query": sec_eval_query(question, [record["ticker"]], fields, "multi_fact", corpus),
                "expected": {
                    "contains": contains,
                    "required_fields": ["companies"],
                    "grounded": True,
                    "ground_truth": {
                        "companies": [{"ticker": record["ticker"], "company": record["company"], "fiscal_year": record["fiscal_year"], **{field: data.get(field) for field in fields}}],
                        "citations": flatten_citations_for_fields(record["citations"], fields),
                    },
                },
            }
        )
        if sum(1 for case in cases if case["category"] == "multi_fact") >= 50:
            break

    comparable = [record for record in records if record["data"].get("revenue_usd") not in (None, "") and record["data"].get("net_income_usd") not in (None, "")]
    compare_fields = ["revenue_usd", "net_income_usd"]
    if len(comparable) < 30:
        comparable = [record for record in records if record["data"].get("revenue_usd") not in (None, "") and record["data"].get("assets_usd") not in (None, "")]
        compare_fields = ["revenue_usd", "assets_usd"]
    for index in range(0, min(len(comparable) - 2, 150), 3):
        trio = comparable[index : index + 3]
        tickers = [record["ticker"] for record in trio]
        rendered_companies = ", ".join(f"{record['ticker']} ({record['fiscal_year']})" for record in trio)
        question = (
            f"Compare {SEC_FIELD_LABELS.get(compare_fields[0], compare_fields[0])} and "
            f"{SEC_FIELD_LABELS.get(compare_fields[1], compare_fields[1])} for "
            f"{rendered_companies}."
        )
        case_id = f"kraft_mc_{sum(1 for case in cases if case['category'] == 'multi_company') + 1:03d}"
        cases.append(
            {
                "case_id": case_id,
                "suite": suite,
                "category": "multi_company",
                "difficulty": "hard_public_replication",
                "topic": "cross_company_comparison",
                "question": question,
                "query": sec_eval_query(question, tickers, compare_fields, "multi_company", corpus),
                "expected": {
                    "contains": tickers,
                    "required_fields": ["companies"],
                    "grounded": True,
                    "ground_truth": {
                        "companies": [
                            {"ticker": record["ticker"], "company": record["company"], "fiscal_year": record["fiscal_year"], **{field: record["data"].get(field) for field in compare_fields}}
                            for record in trio
                        ],
                        "citations": [citation for record in trio for citation in flatten_citations_for_fields(record["citations"], compare_fields)],
                    },
                },
            }
        )
        if sum(1 for case in cases if case["category"] == "multi_company") >= 50:
            break

    derived_specs = [
        ("capex_usd", "revenue_usd", "capex_to_revenue_ratio", "capex as a share of revenue"),
        ("net_income_usd", "revenue_usd", "net_income_margin", "net income margin"),
        ("revenue_usd", "assets_usd", "revenue_to_assets_ratio", "revenue as a share of assets"),
    ]
    used: set[str] = set()
    for numerator, denominator, ratio_field, label in derived_specs:
        for record in records:
            if record["ticker"] in used:
                continue
            data = record["data"]
            if data.get(numerator) in (None, "") or data.get(denominator) in (None, ""):
                continue
            used.add(record["ticker"])
            question = f"For {record['ticker']}, derive {label} from {record['fiscal_year']} 10-K facts and return the source fields."
            case_id = f"kraft_ms_{sum(1 for case in cases if case['category'] == 'multi_step') + 1:03d}"
            cases.append(
                {
                    "case_id": case_id,
                    "suite": suite,
                    "category": "multi_step",
                    "difficulty": "hard_public_replication",
                    "topic": "derived_financial_ratio",
                    "question": question,
                    "query": sec_eval_query(question, [record["ticker"]], [denominator, numerator, ratio_field], "multi_step", corpus),
                    "expected": {
                        "contains": [record["ticker"], str(data[denominator]), str(data[numerator])],
                        "required_fields": ["companies"],
                        "grounded": True,
                        "ground_truth": {
                            "companies": [{"ticker": record["ticker"], "company": record["company"], "fiscal_year": record["fiscal_year"], denominator: data[denominator], numerator: data[numerator]}],
                            "citations": flatten_citations_for_fields(record["citations"], [denominator, numerator]),
                        },
                    },
                }
            )
            if sum(1 for case in cases if case["category"] == "multi_step") >= 50:
                break
        if sum(1 for case in cases if case["category"] == "multi_step") >= 50:
            break

    return balanced_case_limit(cases, limit)


def sec_groundtruth_build(args: argparse.Namespace) -> dict[str, Any]:
    paths = ensure_sec_runtime(args.corpus)
    if paths["groundtruth"].exists() and args.lock and not args.force:
        rows = read_jsonl(paths["groundtruth"])
        return {"status": "groundtruth_locked_exists", "path": str(paths["groundtruth"]), "cases": len(rows)}
    with connect(Path(args.db)) as conn:
        init_schema(conn)
        cases = sec_groundtruth_case_specs(conn, args.corpus, args.suite, args.limit)
        if len(cases) < args.limit:
            raise KnowledgeError(f"Only {len(cases)} ground-truth cases generated; need {args.limit}. Check corpus/companyfacts/text coverage.")
        paths["groundtruth"].write_text("", encoding="utf-8")
        append_jsonl(paths["groundtruth"], cases)
        seed_case_specs(conn, args.suite, [{"id": case["case_id"], **case} for case in cases], args.limit)
    categories = Counter(case["category"] for case in cases)
    return {
        "status": "groundtruth_locked" if args.lock else "groundtruth_written",
        "suite": args.suite,
        "corpus": args.corpus,
        "path": str(paths["groundtruth"]),
        "cases": len(cases),
        "categories": dict(sorted(categories.items())),
        "source_policy": "independent_from_sec_artifacts_companyfacts_first_text_second",
    }


def score_sec_result(result: dict[str, Any], expected: dict[str, Any], retriever: str) -> tuple[bool, float, float]:
    text = answer_text(result)
    contains = expected.get("contains", [])
    term_hits = sum(1 for term in contains if str(term).lower() in text)
    term_score = term_hits / max(1, len(contains))
    if retriever == "compiled":
        companies = result.get("answer", {}).get("companies", [])
        citation_coverage = 1.0 if result.get("citations") else 0.0
        field_score_value = 1.0 if companies else 0.0
    else:
        citation_coverage = 0.0
        field_score_value = 1.0 if result.get("answer", {}).get("snippets") else 0.0
    score = round((term_score * 0.55) + (field_score_value * 0.30) + (citation_coverage * 0.15), 4)
    passed = score >= 0.75 and (retriever != "compiled" or citation_coverage >= 0.99)
    return passed, score, citation_coverage


def classify_sec_failure(result: dict[str, Any], expected: dict[str, Any], retriever: str, citation_coverage: float) -> str:
    text = answer_text(result)
    warnings = result.get("warnings", [])
    if retriever == "compiled" and citation_coverage < 0.99:
        return "citation_missing"
    if any(str(warning).startswith("missing_sec_artifact") for warning in warnings):
        return "missing_fact"
    answer = result.get("answer", {})
    if retriever == "compiled" and not answer.get("companies"):
        return "missing_fact"
    if retriever != "compiled" and not answer.get("snippets"):
        return "missing_fact"
    missing_terms = [str(term) for term in expected.get("contains", []) if str(term).lower() not in text]
    ticker_like = [term for term in missing_terms if re.fullmatch(r"[A-Z][A-Z0-9.-]{0,6}", term)]
    if ticker_like:
        return "wrong_entity"
    if missing_terms:
        if any(re.fullmatch(r"-?\d+(?:\.\d+)?", term.replace(",", "")) for term in missing_terms):
            return "missing_fact"
        return "extraction_miss"
    if any("section" in str(warning) for warning in warnings):
        return "section_parse_failure"
    return "judge_disagreement"


def run_sec_retriever(conn: sqlite3.Connection, retriever: str, query: dict[str, Any], corpus: str) -> dict[str, Any]:
    if retriever == "compiled":
        return run_sec_compiled_query(conn, query, corpus)
    if retriever == "agentic_rag":
        return run_sec_agentic_rag_query(conn, query, corpus)
    if retriever in {"coding_sandbox", "coding_agent"}:
        return run_sec_coding_sandbox_query(conn, query, corpus)
    raise KnowledgeError(f"unknown SEC retriever: {retriever}")


def sec_corpus_profile(conn: sqlite3.Connection, corpus: str) -> dict[str, Any]:
    filing_count = conn.execute("SELECT COUNT(*) AS n FROM sec_filings WHERE corpus = ?", (corpus,)).fetchone()["n"]
    artifact_count = conn.execute("SELECT COUNT(*) AS n FROM sec_artifacts WHERE corpus = ?", (corpus,)).fetchone()["n"]
    chunk_count = conn.execute("SELECT COUNT(*) AS n FROM sec_chunks WHERE corpus = ?", (corpus,)).fetchone()["n"]
    normalized_bytes = conn.execute("SELECT COALESCE(SUM(normalized_byte_count), 0) AS n FROM sec_filings WHERE corpus = ?", (corpus,)).fetchone()["n"]
    year_distribution = {
        str(row["fiscal_year"]): row["n"]
        for row in conn.execute("SELECT fiscal_year, COUNT(*) AS n FROM sec_filings WHERE corpus = ? GROUP BY fiscal_year ORDER BY fiscal_year", (corpus,))
    }
    latest_artifacts = [(row, row_json(row, "data_json", {})) for row in sec_available_artifacts(conn, corpus)]
    latest_year_distribution = Counter(str(data.get("fiscal_year")) for _, data in latest_artifacts)
    coverage_fields = [
        "revenue_usd",
        "net_income_usd",
        "assets_usd",
        "capex_usd",
        "r_and_d_usd",
        "share_repurchases_usd",
        "operating_cash_flow_usd",
        "employees",
        "risk_factor_summary",
        "segments",
        "acquisitions",
    ]
    field_coverage = {
        field: sum(1 for _, data in latest_artifacts if data.get(field) not in (None, "", []))
        for field in coverage_fields
    }
    return {
        "filings": filing_count,
        "artifacts": artifact_count,
        "chunks": chunk_count,
        "normalized_bytes": normalized_bytes,
        "normalized_mib": round(normalized_bytes / (1024 * 1024), 3),
        "latest_company_artifacts": len(latest_artifacts),
        "year_distribution": year_distribution,
        "latest_year_distribution": dict(sorted(latest_year_distribution.items())),
        "latest_field_coverage": field_coverage,
    }


def run_sec_eval(conn: sqlite3.Connection, suite: str, retrievers: list[str], corpus: str, limit: int = 150) -> dict[str, Any]:
    if suite not in {SEC_SUITE_NAME, KRAFT_PUBLIC_SUITE_NAME}:
        raise KnowledgeError(f"unknown SEC suite: {suite}")
    init_schema(conn)
    if suite == KRAFT_PUBLIC_SUITE_NAME:
        seed_kraft_eval_cases_from_locked(conn, corpus, suite, limit)
    else:
        seed_sec_eval_cases(conn, corpus, limit)
    rows = list(conn.execute("SELECT * FROM eval_cases WHERE suite = ? ORDER BY category, id LIMIT ?", (suite, limit)))
    summaries: dict[str, Any] = {}
    run_rows = []
    for retriever in retrievers:
        results = []
        for row in rows:
            query = json_loads(row["query_json"], {})
            expected = json_loads(row["expected_json"], {})
            started = time.perf_counter()
            result = run_sec_retriever(conn, retriever, query, corpus)
            latency_ms = (time.perf_counter() - started) * 1000.0
            passed, score, citation_coverage = score_sec_result(result, expected, retriever)
            failure_category = "" if passed else classify_sec_failure(result, expected, retriever, citation_coverage)
            budget = result.get("budget_used", {})
            source_bytes = int(budget.get("source_bytes_proxy", 0))
            steps = int(budget.get("steps", 1))
            run_rows.append(
                (
                    stable_id(suite, retriever, row["id"], utc_now(), length=24),
                    suite,
                    retriever,
                    row["id"],
                    1 if passed else 0,
                    score,
                    latency_ms,
                    source_bytes,
                    steps,
                    citation_coverage,
                    json_dumps(result),
                    utc_now(),
                )
            )
            results.append(
                {
                    "case_id": row["id"],
                    "category": row["category"],
                    "passed": passed,
                    "score": score,
                    "latency_ms": round(latency_ms, 3),
                    "source_bytes": source_bytes,
                    "steps": steps,
                    "citation_coverage": round(citation_coverage, 3),
                    "failure_category": failure_category,
                }
            )
        passed_count = sum(1 for item in results if item["passed"])
        latencies = sorted(item["latency_ms"] for item in results)
        failures = Counter(item["failure_category"] for item in results if item["failure_category"])
        summaries[retriever] = {
            "cases": len(results),
            "passed": passed_count,
            "completion_rate": round(passed_count / max(1, len(results)), 3),
            "average_score": round(sum(item["score"] for item in results) / max(1, len(results)), 4),
            "median_latency_ms": latencies[len(latencies) // 2] if latencies else 0,
            "total_source_bytes_proxy": sum(item["source_bytes"] for item in results),
            "average_steps": round(sum(item["steps"] for item in results) / max(1, len(results)), 3),
            "average_citation_coverage": round(sum(item["citation_coverage"] for item in results) / max(1, len(results)), 3),
            "failure_categories": dict(sorted(failures.items())),
            "results": results,
        }
    with conn:
        conn.executemany(
            """
            INSERT INTO eval_runs
              (id, suite, retriever, case_id, passed, score, latency_ms, source_bytes,
               steps, citation_coverage, answer_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            run_rows,
        )
    if "compiled" in summaries and "agentic_rag" in summaries:
        rag_bytes = max(1, summaries["agentic_rag"]["total_source_bytes_proxy"])
        comp_bytes = max(1, summaries["compiled"]["total_source_bytes_proxy"])
        summaries["comparison"] = {
            "compiled_vs_agentic_rag_source_byte_reduction_x": round(rag_bytes / comp_bytes, 3),
            "compiled_completion_target_met": summaries["compiled"]["completion_rate"] >= 0.9,
            "compiled_latency_target_met": summaries["compiled"]["median_latency_ms"] < summaries["agentic_rag"]["median_latency_ms"],
            "compiled_citation_target_met": summaries["compiled"]["average_citation_coverage"] >= 0.99,
            "compiled_steps_target_met": summaries["compiled"]["average_steps"] <= 2,
            "compiled_source_reduction_target_met": (rag_bytes / comp_bytes) >= 5,
        }
    return {"suite": suite, "corpus": corpus, "retrievers": retrievers, "corpus_profile": sec_corpus_profile(conn, corpus), "summary": summaries}


def sec_analysis_markdown(result: dict[str, Any]) -> str:
    summary = result.get("summary", {})
    profile = result.get("corpus_profile", {})
    retrievers = [name for name in result.get("retrievers", []) if name in summary]
    lines = [
        f"# SEC 10-K Nexus-like Evaluation: {result.get('corpus')}",
        "",
        f"- Generated at: {utc_now()}",
        f"- Suite: `{result.get('suite')}`",
        "- Corpus note: HF SEC 10-K mirror experiment; not Pinecone private KRAFTBench and not the official 2022 EDGAR corpus.",
        f"- Corpus size: {profile.get('filings', 0)} filings, {profile.get('latest_company_artifacts', 0)} latest-company artifacts, "
        f"{profile.get('chunks', 0)} chunks, {profile.get('normalized_mib', 0)} MiB normalized text.",
        "",
        "## Corpus Profile",
        "",
        f"- Filing years: {json_dumps(profile.get('year_distribution', {}))}",
        f"- Latest artifact years: {json_dumps(profile.get('latest_year_distribution', {}))}",
        f"- Latest field coverage: {json_dumps(profile.get('latest_field_coverage', {}))}",
        "",
        "## Raw Data Table",
        "",
        "| retriever | cases | passed | completion | avg score | median latency ms | total source bytes | avg steps | citation coverage |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for retriever in retrievers:
        item = summary[retriever]
        lines.append(
            "| {name} | {cases} | {passed} | {completion:.3f} | {score:.4f} | {latency} | {bytes} | {steps:.3f} | {citation:.3f} |".format(
                name=retriever,
                cases=item["cases"],
                passed=item["passed"],
                completion=item["completion_rate"],
                score=item["average_score"],
                latency=item["median_latency_ms"],
                bytes=item["total_source_bytes_proxy"],
                steps=item["average_steps"],
                citation=item["average_citation_coverage"],
            )
        )

    comparison = summary.get("comparison", {})
    lines.extend(["", "## Key Findings", ""])
    if "compiled" in summary:
        compiled = summary["compiled"]
        lines.append(
            f"1. Compiled artifacts completed {compiled['passed']}/{compiled['cases']} cases "
            f"({compiled['completion_rate']:.3f}) with citation coverage {compiled['average_citation_coverage']:.3f}."
        )
    if "agentic_rag" in summary and "compiled" in summary:
        rag = summary["agentic_rag"]
        compiled = summary["compiled"]
        reduction = comparison.get("compiled_vs_agentic_rag_source_byte_reduction_x", 0)
        lines.append(
            f"2. Compiled used {compiled['total_source_bytes_proxy']} source-byte proxy versus "
            f"{rag['total_source_bytes_proxy']} for agentic RAG, a {reduction}x reduction."
        )
        lines.append(
            f"3. Median latency was {compiled['median_latency_ms']} ms for compiled and "
            f"{rag['median_latency_ms']} ms for agentic RAG."
        )
    if comparison:
        gate_text = ", ".join(f"{key}={value}" for key, value in comparison.items() if key.endswith("_target_met"))
        lines.append(f"4. Acceptance gates: {gate_text}.")

    lines.extend(["", "## Failure Categories", ""])
    for retriever in retrievers:
        failures = summary[retriever].get("failure_categories", {})
        rendered = ", ".join(f"{key}: {value}" for key, value in failures.items()) or "none"
        lines.append(f"- `{retriever}`: {rendered}")

    lines.extend(
        [
            "",
            "## Suggested Next Experiments",
            "",
            "1. Run the same pipeline on the official SEC 2022 corpus once SEC network access is reliable.",
            "2. Add a human/LLM pass over `judge_pack.jsonl` to separate retrieval misses from weak deterministic extraction.",
            "3. Tune text extraction only on failed cases, then rerun with the same fixed manifest.",
            "",
        ]
    )
    return "\n".join(lines)


def write_sec_analysis_outputs(corpus: str, result: dict[str, Any]) -> dict[str, str]:
    paths = ensure_sec_runtime(corpus)
    comparison_path = paths["judge"] / "comparison_summary.json"
    report_path = paths["judge"] / "analysis_report.md"
    write_json_file(comparison_path, result)
    report_path.write_text(sec_analysis_markdown(result), encoding="utf-8")
    return {"comparison_summary": str(comparison_path), "analysis_report": str(report_path)}


def load_eval_cases_for_suite(conn: sqlite3.Connection, suite: str, corpus: str, limit: int) -> list[sqlite3.Row]:
    if suite == KRAFT_PUBLIC_SUITE_NAME:
        seed_kraft_eval_cases_from_locked(conn, corpus, suite, limit)
    elif suite == SEC_SUITE_NAME:
        seed_sec_eval_cases(conn, corpus, limit)
    else:
        raise KnowledgeError(f"unknown SEC suite: {suite}")
    return list(conn.execute("SELECT * FROM eval_cases WHERE suite = ? ORDER BY category, id LIMIT ?", (suite, limit)))


def token_proxy_from_budget(budget: dict[str, Any]) -> int:
    return max(1, int(int(budget.get("source_bytes_proxy", 0) or 0) / 4))


def sec_agent_pack(args: argparse.Namespace) -> dict[str, Any]:
    retrievers = normalize_sec_retrievers(args.retriever)
    paths = ensure_sec_runtime(args.corpus)
    rows: list[dict[str, Any]] = []
    draft_answers: list[dict[str, Any]] = []
    with connect(Path(args.db)) as conn:
        init_schema(conn)
        cases = load_eval_cases_for_suite(conn, args.suite, args.corpus, args.limit)
        for case in cases:
            query = json_loads(case["query_json"], {})
            for retriever in retrievers:
                evidence = run_sec_retriever(conn, retriever, query, args.corpus)
                budget = evidence.get("budget_used", {})
                task_id = stable_id(args.suite, args.corpus, case["id"], retriever, length=24)
                task = {
                    "task_id": task_id,
                    "suite": args.suite,
                    "corpus": args.corpus,
                    "case_id": case["id"],
                    "category": case["category"],
                    "retriever": retriever,
                    "composer": args.composer,
                    "budget_seconds": args.budget_seconds,
                    "token_budget": args.token_budget,
                    "question": case["question"],
                    "retrieval_evidence": evidence,
                    "budget_used": {
                        **budget,
                        "token_proxy": token_proxy_from_budget(budget),
                    },
                    "composer_instruction": (
                        "Answer the question using only retrieval_evidence. Return JSON with answer_text, "
                        "citations, completed, and uncertainty_notes. Do not use hidden ground truth."
                    ),
                }
                rows.append(task)
                draft_answers.append(
                    {
                        "task_id": task_id,
                        "suite": args.suite,
                        "corpus": args.corpus,
                        "case_id": case["id"],
                        "retriever": retriever,
                        "composer": "draft_from_retriever_not_codex",
                        "completed": bool(answer_text(evidence).strip()),
                        "answer_text": answer_text(evidence)[:6000],
                        "citations": evidence.get("citations", []),
                        "budget_used": task["budget_used"],
                        "warnings": ["draft_answer_for_pipeline_smoke_only_not_official_accuracy"],
                    }
                )
    paths["agent_pack"].write_text("", encoding="utf-8")
    append_jsonl(paths["agent_pack"], rows)
    paths["agent_answers_draft"].write_text("", encoding="utf-8")
    append_jsonl(paths["agent_answers_draft"], draft_answers)
    return {
        "status": "agent_pack_written",
        "suite": args.suite,
        "corpus": args.corpus,
        "path": str(paths["agent_pack"]),
        "draft_answers_path": str(paths["agent_answers_draft"]),
        "tasks": len(rows),
        "retrievers": retrievers,
        "composer": args.composer,
        "note": "Draft answers are for smoke testing only; official accuracy requires Codex-composed agent_answers.jsonl.",
    }


def normalize_agent_answer(row: dict[str, Any]) -> dict[str, Any]:
    retriever = normalize_sec_retrievers(str(row.get("retriever", "")))[0]
    answer_value = row.get("answer_text", row.get("answer", ""))
    if isinstance(answer_value, (dict, list)):
        answer_value = json_dumps(answer_value)
    return {
        "task_id": str(row.get("task_id") or stable_id(str(row.get("suite", "")), str(row.get("case_id", "")), retriever, length=24)),
        "suite": str(row.get("suite", "")),
        "corpus": str(row.get("corpus", "")),
        "case_id": str(row.get("case_id", "")),
        "retriever": retriever,
        "composer": str(row.get("composer", "codex")),
        "completed": bool(row.get("completed", True)),
        "answer_text": str(answer_value),
        "citations": row.get("citations", []),
        "budget_used": row.get("budget_used", {}),
        "warnings": row.get("warnings", []),
    }


def sec_agent_import(args: argparse.Namespace) -> dict[str, Any]:
    paths = ensure_sec_runtime(args.corpus)
    source = Path(args.input)
    if not source.exists():
        raise KnowledgeError(f"agent answer input missing: {source}")
    rows = [normalize_agent_answer(row) for row in read_jsonl(source)]
    if not rows:
        raise KnowledgeError(f"no agent answers found in {source}")
    paths["agent_answers"].write_text("", encoding="utf-8")
    append_jsonl(paths["agent_answers"], rows)
    by_retriever = Counter(row["retriever"] for row in rows)
    completed = Counter(row["retriever"] for row in rows if row["completed"])
    return {
        "status": "agent_answers_imported",
        "path": str(paths["agent_answers"]),
        "answers": len(rows),
        "by_retriever": dict(sorted(by_retriever.items())),
        "completed_by_retriever": dict(sorted(completed.items())),
    }


def grouped_agent_answers(path: Path) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in read_jsonl(path):
        grouped.setdefault(str(row.get("case_id", "")), []).append(row)
    return grouped


def sec_blind_judge_pack(args: argparse.Namespace) -> dict[str, Any]:
    paths = ensure_sec_runtime(args.corpus)
    if not paths["agent_answers"].exists():
        raise KnowledgeError(f"agent answers missing: {paths['agent_answers']}. Run sec-agent-import first.")
    answers_by_case = grouped_agent_answers(paths["agent_answers"])
    key: dict[str, dict[str, str]] = {}
    rows = []
    with connect(Path(args.db)) as conn:
        init_schema(conn)
        cases = load_eval_cases_for_suite(conn, args.suite, args.corpus, args.limit)
        for case in cases:
            expected = json_loads(case["expected_json"], {})
            answers = []
            for answer in answers_by_case.get(case["id"], []):
                answer_id = stable_id(args.suite, case["id"], answer["retriever"], "blind", length=16)
                key[answer_id] = {"case_id": case["id"], "retriever": answer["retriever"]}
                answers.append(
                    {
                        "answer_id": answer_id,
                        "answer_text": answer.get("answer_text", ""),
                        "citations": answer.get("citations", []),
                        "completed": answer.get("completed", False),
                        "budget_used": answer.get("budget_used", {}),
                    }
                )
            rng = random.Random(int(stable_id(args.suite, case["id"], "judge-order", length=12), 16))
            rng.shuffle(answers)
            rows.append(
                {
                    "case_id": case["id"],
                    "category": case["category"],
                    "question": case["question"],
                    "ground_truth": expected.get("ground_truth", expected),
                    "answers": answers,
                    "judge": args.judge,
                    "judge_instruction": (
                        "Blindly grade each answer for factual accuracy against ground_truth and citations. "
                        "Return JSONL with case_id and judgements: answer_id, passed, accuracy_score in [0,1], "
                        "failure_category, rationale. Do not infer retriever identity."
                    ),
                }
            )
    out_path = Path(args.output) if args.output else paths["judge_pack_blind"]
    out_path.write_text("", encoding="utf-8")
    append_jsonl(out_path, rows)
    write_json_file(paths["judge_answer_key"], {"created_at": utc_now(), "suite": args.suite, "corpus": args.corpus, "key": key})
    return {
        "status": "blind_judge_pack_written",
        "path": str(out_path),
        "answer_key_path": str(paths["judge_answer_key"]),
        "cases": len(rows),
        "judge": args.judge,
    }


def sec_judge_pack(args: argparse.Namespace) -> dict[str, Any]:
    if getattr(args, "blind", False):
        return sec_blind_judge_pack(args)
    retrievers = [item.strip() for item in args.compare.split(",") if item.strip()]
    paths = ensure_sec_runtime(args.corpus)
    out_path = Path(args.output) if args.output else paths["judge"] / "judge_pack.jsonl"
    with connect(Path(args.db)) as conn:
        init_schema(conn)
        seed_sec_eval_cases(conn, args.corpus, args.limit)
        cases = list(conn.execute("SELECT * FROM eval_cases WHERE suite = ? ORDER BY category, id LIMIT ?", (args.suite, args.limit)))
        rows = []
        for case in cases:
            query = json_loads(case["query_json"], {})
            expected = json_loads(case["expected_json"], {})
            answers = {}
            for retriever in retrievers:
                answers[retriever] = run_sec_retriever(conn, retriever, query, args.corpus)
            rows.append(
                {
                    "case_id": case["id"],
                    "category": case["category"],
                    "question": case["question"],
                    "ground_truth_hints": expected,
                    "answers": answers,
                    "judge_instruction": "Grade factual accuracy against SEC citations and hints. Return pass/fail per retriever plus failure category.",
                }
            )
    out_path.write_text("", encoding="utf-8")
    append_jsonl(out_path, rows)
    return {"status": "judge_pack_written", "path": str(out_path), "cases": len(rows), "retrievers": retrievers}


def extract_judgement_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(row.get("judgements"), list):
        return row["judgements"]
    if isinstance(row.get("judgments"), list):
        return row["judgments"]
    if isinstance(row.get("answers"), list):
        return row["answers"]
    return [row]


def bool_from_judge_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value >= 0.5
    return str(value).strip().lower() in {"true", "pass", "passed", "yes", "1", "accurate"}


def proportion_ci(values: list[float]) -> list[float]:
    if not values:
        return [0.0, 0.0]
    mean = sum(values) / len(values)
    stderr = math.sqrt(max(0.0, mean * (1.0 - mean)) / max(1, len(values)))
    return [round(max(0.0, mean - 1.96 * stderr), 4), round(min(1.0, mean + 1.96 * stderr), 4)]


def summarize_judge_results(rows: list[dict[str, Any]], agent_answers: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["retriever"], []).append(row)
    answers_by_retriever: dict[str, list[dict[str, Any]]] = {}
    for row in agent_answers:
        answers_by_retriever.setdefault(row["retriever"], []).append(row)
    summary: dict[str, Any] = {}
    for retriever, items in grouped.items():
        pass_values = [1.0 if item["passed"] else 0.0 for item in items]
        scores = [float(item.get("accuracy_score", pass_values[index])) for index, item in enumerate(items)]
        answer_rows = answers_by_retriever.get(retriever, [])
        budgets = [row.get("budget_used", {}) for row in answer_rows]
        latencies = [float(budget.get("latency_ms", 0.0) or 0.0) for budget in budgets]
        token_proxies = [int(budget.get("token_proxy", token_proxy_from_budget(budget)) or 0) for budget in budgets]
        steps = [int(budget.get("steps", 0) or 0) for budget in budgets]
        failure_categories = Counter(item.get("failure_category", "") for item in items if item.get("failure_category"))
        summary[retriever] = {
            "judged_cases": len(items),
            "passed": int(sum(pass_values)),
            "accuracy": round(sum(scores) / max(1, len(scores)), 4),
            "pass_rate": round(sum(pass_values) / max(1, len(pass_values)), 4),
            "accuracy_ci95": proportion_ci(pass_values),
            "completion": round(sum(1 for row in answer_rows if row.get("completed")) / max(1, len(answer_rows)), 4) if answer_rows else 0.0,
            "average_latency_s": round((sum(latencies) / max(1, len(latencies))) / 1000.0, 4) if latencies else 0.0,
            "average_token_proxy": round(sum(token_proxies) / max(1, len(token_proxies)), 2) if token_proxies else 0.0,
            "average_steps": round(sum(steps) / max(1, len(steps)), 3) if steps else 0.0,
            "failure_categories": dict(sorted(failure_categories.items())),
        }
    return summary


def sec_judge_import(args: argparse.Namespace) -> dict[str, Any]:
    paths = ensure_sec_runtime(args.corpus)
    source = Path(args.input)
    if not source.exists():
        raise KnowledgeError(f"judge result input missing: {source}")
    answer_key = load_json_file(paths["judge_answer_key"], {}).get("key", {})
    if not answer_key:
        raise KnowledgeError(f"blind answer key missing: {paths['judge_answer_key']}. Run sec-judge-pack --blind first.")
    normalized = []
    for row in read_jsonl(source):
        case_id = str(row.get("case_id", ""))
        for item in extract_judgement_items(row):
            answer_id = str(item.get("answer_id", ""))
            mapping = answer_key.get(answer_id, {})
            if not mapping:
                continue
            accuracy_score = float(item.get("accuracy_score", 1.0 if bool_from_judge_value(item.get("passed", False)) else 0.0))
            normalized.append(
                {
                    "case_id": case_id or mapping.get("case_id", ""),
                    "answer_id": answer_id,
                    "retriever": mapping.get("retriever", ""),
                    "passed": bool_from_judge_value(item.get("passed", accuracy_score >= 0.5)),
                    "accuracy_score": max(0.0, min(1.0, accuracy_score)),
                    "failure_category": str(item.get("failure_category", "")),
                    "rationale": str(item.get("rationale", "")),
                    "judge": args.judge,
                }
            )
    if not normalized:
        raise KnowledgeError(f"no valid blinded judgements found in {source}")
    paths["judge_results"].write_text("", encoding="utf-8")
    append_jsonl(paths["judge_results"], normalized)
    agent_answers = read_jsonl(paths["agent_answers"])
    summary = {
        "status": "judge_results_imported",
        "suite": args.suite,
        "corpus": args.corpus,
        "judge": args.judge,
        "results": summarize_judge_results(normalized, agent_answers),
    }
    write_json_file(paths["judge_summary"], summary)
    return {**summary, "path": str(paths["judge_results"]), "summary_path": str(paths["judge_summary"])}


def official_delta_rows(local_summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for retriever, official in OFFICIAL_PINECONE_KRAFT_METRICS.items():
        local = local_summary.get(retriever) or local_summary.get("coding_sandbox" if retriever == "coding_agent" else retriever) or {}
        rows.append(
            {
                "retriever": retriever,
                "official_label": official["label"],
                "official_completion": official["completion"],
                "local_completion": local.get("completion", local.get("completion_rate")),
                "official_accuracy": official["accuracy"],
                "local_accuracy": local.get("accuracy", local.get("average_score")),
                "official_latency_avg_s": official["latency_avg_s"],
                "local_latency_avg_s": local.get("average_latency_s"),
                "official_tokens_avg": official["tokens_avg"],
                "local_token_proxy_avg": local.get("average_token_proxy"),
                "official_steps_avg": official["steps_avg"],
                "local_steps_avg": local.get("average_steps"),
            }
        )
    return rows


def kraft_analysis_markdown(corpus: str, suite: str, audit: dict[str, Any], judge_summary: dict[str, Any], delta_rows: list[dict[str, Any]]) -> str:
    status = "public_method_reproduction"
    corpus_blocked = audit.get("blocked_official_download") or not audit.get("corpus_gate", {}).get("official_download_complete")
    judge_missing = not judge_summary.get("results")
    if corpus_blocked and judge_missing:
        status = "partial_reproduction_blocked_by_corpus_and_pending_codex_judge"
    elif corpus_blocked:
        status = "partial_reproduction_blocked_by_corpus"
    elif judge_missing:
        status = "partial_reproduction_pending_codex_judge"
    lines = [
        f"# KRAFTBench-like Public Reproduction: {corpus}",
        "",
        f"- Generated at: {utc_now()}",
        f"- Suite: `{suite}`",
        f"- Status: `{status}`",
        "- Boundary: public-method reproduction only; not Pinecone private KRAFTBench and not Pinecone Nexus internals.",
        "",
        "## Corpus Audit",
        "",
        f"- Downloaded filings: {audit.get('downloaded_filings', 0)}",
        f"- Normalized MB: {audit.get('normalized_mb', 0)}",
        f"- Gate: {json_dumps(audit.get('corpus_gate', {}))}",
        f"- Blocked official download: {audit.get('blocked_official_download', False)}",
        "",
        "## Official Delta Table",
        "",
        "| retriever | local completion | official completion | local accuracy | official accuracy | local latency s | official latency s | local token_proxy | official tokens | local steps | official steps |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in delta_rows:
        lines.append(
            "| {retriever} | {lc} | {oc} | {la} | {oa} | {ll} | {ol} | {lt} | {ot} | {ls} | {os} |".format(
                retriever=row["retriever"],
                lc=row.get("local_completion"),
                oc=row.get("official_completion"),
                la=row.get("local_accuracy"),
                oa=row.get("official_accuracy"),
                ll=row.get("local_latency_avg_s"),
                ol=row.get("official_latency_avg_s"),
                lt=row.get("local_token_proxy_avg"),
                ot=row.get("official_tokens_avg"),
                ls=row.get("local_steps_avg"),
                os=row.get("official_steps_avg"),
            )
        )
    lines.extend(["", "## Judge Summary", "", json.dumps(judge_summary.get("results", {}), ensure_ascii=False, indent=2), ""])
    return "\n".join(lines)


def sec_analysis(args: argparse.Namespace) -> dict[str, Any]:
    paths = ensure_sec_runtime(args.corpus)
    audit = load_json_file(paths["manifest_audit"], {}) or audit_sec_corpus(args.corpus)
    judge_summary = load_json_file(paths["judge_summary"], {})
    local_summary = judge_summary.get("results", {})
    if not local_summary:
        comparison = load_json_file(paths["judge"] / "comparison_summary.json", {})
        local_summary = comparison.get("summary", {}) if comparison else {}
    delta_rows = official_delta_rows(local_summary) if args.compare_official_pinecone else []
    write_json_file(paths["official_delta"], {"suite": args.suite, "corpus": args.corpus, "rows": delta_rows, "official_source": "Pinecone public Nexus/KRAFTBench blog"})
    paths["kraft_report"].write_text(kraft_analysis_markdown(args.corpus, args.suite, audit, judge_summary, delta_rows), encoding="utf-8")
    return {
        "status": "kraft_analysis_written",
        "suite": args.suite,
        "corpus": args.corpus,
        "report_path": str(paths["kraft_report"]),
        "official_delta_path": str(paths["official_delta"]),
        "has_judge_results": bool(judge_summary.get("results")),
        "audit_status": audit.get("status", "missing"),
    }


def default_query(question: str, contexts: list[str], fields: list[str], depth: str = "standard") -> dict[str, Any]:
    return {
        "ask": question,
        "contexts": contexts,
        "where": {"principal_tags": ["public", "maintainer"]},
        "ground": True,
        "shape": {"type": "object", "properties": {field: {"type": "string"} for field in fields}},
        "confidence": {"min": 0.7},
        "budget": {"depth": depth, "latency_ms": 1000, "max_artifacts": 8},
    }


def eval_case_specs() -> list[dict[str, Any]]:
    raw_cases = [
        ("single_doc", "What is Meta_workflow's project purpose?", ["meta_project"], ["purpose"], ["business workflow design", "memory"]),
        ("single_doc", "Who are the target users for Meta_workflow?", ["meta_project", "architecture"], ["target_users"], ["project owners", "Codex"]),
        ("single_doc", "What does AGENTS.md say about hard boundaries?", ["meta_project"], ["hard_boundaries"], ["Pro is external advice", "runtime registries"]),
        ("single_doc", "Where should stable architecture direction be recorded?", ["meta_project"], ["decision_placement"], ["docs/architecture"]),
        ("single_doc", "What is the local work loop for substantial work?", ["meta_project"], ["local_work_loop"], ["inspect repo state", "validate"]),
        ("single_doc", "List the architecture engine subsystems.", ["architecture"], ["engine_subsystems"], ["Intake", "Orchestrator", "Memory and Recall"]),
        ("single_doc", "What are the V1 success criteria?", ["architecture"], ["v1_success_criteria"], ["workflow spec", "Memory writeback"]),
        ("single_doc", "What are the architecture roadmap phases?", ["architecture"], ["roadmap"], ["Phase 1", "Phase 4"]),
        ("single_doc", "What is the MAP core lesson?", ["methodology"], ["map_core_lesson"], ["specialized functions", "durable memory"]),
        ("single_doc", "What MAP design principles should Meta_workflow follow?", ["methodology"], ["design_principles"], ["functional modules", "source-grounded evidence"]),
        ("cross_doc", "How does MAP's Monitor relate to Pro validation gates?", ["methodology", "governance"], ["map_module_mapping", "before_memory_or_workflow_writeback"], ["Monitor", "schema_valid"]),
        ("cross_doc", "Connect memory writeback rules across architecture and Pro Bridge.", ["architecture", "pro_bridge", "governance"], ["v1_success_criteria", "feedback_absorption_rules"], ["Memory writeback", "later local gate"]),
        ("cross_doc", "What should happen before Pro advice becomes project truth?", ["meta_project", "pro_bridge", "governance"], ["external_advice_policy", "before_memory_or_workflow_writeback"], ["local verification", "adoption decision"]),
        ("cross_doc", "Which repository paths support the first Pro architecture review?", ["meta_project", "pro_bridge"], ["repository_map", "required_prompt_evidence"], ["docs/methodology", "source_ref"]),
        ("cross_doc", "How should external expert work be routed and governed?", ["meta_project", "pro_bridge"], ["decision_placement", "pro_review_flow"], ["integrations/pro_bridge", "validate-response"]),
        ("cross_doc", "What is needed to resume safely after a Pro trust defect?", ["governance", "pro_bridge"], ["pause_triggers", "resume_rule"], ["recorded", "resolved"]),
        ("cross_doc", "How do runtime outputs and hard boundaries relate?", ["meta_project", "governance"], ["hard_boundaries", "runtime_exclusions"], ["cookies", "raw Pro responses"]),
        ("cross_doc", "How should source evidence be attached to external review?", ["methodology", "pro_bridge"], ["design_principles", "required_prompt_evidence"], ["source-grounded evidence", "source_paths"]),
        ("cross_doc", "Which roadmap phase introduces schemas and event logs?", ["architecture", "methodology"], ["roadmap", "meta_workflow_extensions"], ["phase_1", "Event Log"]),
        ("cross_doc", "How does the Pro Bridge flow end before memory writeback?", ["pro_bridge", "governance"], ["pro_review_flow", "before_memory_or_workflow_writeback"], ["external_feedback_intake", "local decision gate"]),
        ("governance", "What direct mutations are forbidden for Pro responses?", ["meta_project", "pro_bridge"], ["hard_boundaries", "pro_boundary"], ["cannot directly change rules", "acceptance"]),
        ("governance", "What fields are required in Pro prompt evidence?", ["pro_bridge"], ["required_prompt_evidence"], ["source_repo", "expected_output_schema"]),
        ("governance", "What are the safe rollback actions when a Pro gate fails?", ["governance"], ["safe_rollback_actions"], ["do not send", "mark the run blocked"]),
        ("governance", "Which outputs are public and which are runtime-only?", ["governance"], ["public_outputs", "runtime_exclusions"], ["protocols", "local ledgers"]),
        ("governance", "What must be recorded for formal structured Pro review records?", ["pro_bridge"], ["common_record_fields"], ["prompt_hash", "response_hash"]),
        ("pro_bridge", "What CLI flow does Pro Bridge document for review?", ["pro_bridge"], ["pro_review_flow"], ["project-sessions", "watch/capture"]),
        ("pro_bridge", "What validates a Pro response before writeback?", ["governance", "pro_bridge"], ["before_memory_or_workflow_writeback", "feedback_absorption_rules"], ["validate-response", "external feedback intake"]),
        ("pro_bridge", "What source ref rule applies to formal Pro review?", ["pro_bridge"], ["source_ref_rule"], ["block reason", "final source-grounded review"]),
        ("pro_bridge", "Which Pro Bridge runtime ledgers are defined?", ["pro_bridge"], ["runtime_ledgers"], ["pro_project_sessions.jsonl", "external_feedback_ledger.jsonl"]),
        ("pro_bridge", "What completion format makes a Pro response formal?", ["pro_bridge"], ["formal_response_completion"], ["PRO_RESPONSE", "confidence"]),
    ]
    cases = []
    for index, (category, question, contexts, fields, expected_terms) in enumerate(raw_cases, start=1):
        cases.append(
            {
                "id": f"mw30_{index:02d}",
                "suite": SUITE_NAME,
                "category": category,
                "question": question,
                "query": default_query(question, contexts, fields),
                "expected": {
                    "contains": expected_terms,
                    "required_fields": fields,
                    "grounded": True,
                },
            }
        )
    return cases


def seed_eval_cases(conn: sqlite3.Connection) -> dict[str, Any]:
    init_schema(conn)
    now = utc_now()
    cases = eval_case_specs()
    with conn:
        for case in cases:
            conn.execute(
                """
                INSERT INTO eval_cases (id, suite, category, question, query_json, expected_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  suite = excluded.suite,
                  category = excluded.category,
                  question = excluded.question,
                  query_json = excluded.query_json,
                  expected_json = excluded.expected_json,
                  created_at = excluded.created_at
                """,
                (
                    case["id"],
                    case["suite"],
                    case["category"],
                    case["question"],
                    json_dumps(case["query"]),
                    json_dumps(case["expected"]),
                    now,
                ),
            )
    return {"status": "seeded", "suite": SUITE_NAME, "case_count": len(cases)}


def answer_text(result: dict[str, Any]) -> str:
    return json_dumps(result.get("answer", {})).lower()


def score_result(result: dict[str, Any], expected: dict[str, Any], retriever: str) -> tuple[bool, float, float]:
    text = answer_text(result)
    terms = expected.get("contains", [])
    term_hits = sum(1 for term in terms if str(term).lower() in text)
    term_score = term_hits / max(1, len(terms))
    fields = result.get("fields", {})
    required_fields = expected.get("required_fields", [])
    field_hits = 0
    grounded_hits = 0
    for field in required_fields:
        item = fields.get(field)
        if item and item.get("value") not in (None, "", []):
            field_hits += 1
            if item.get("citations"):
                grounded_hits += 1
    field_score_value = field_hits / max(1, len(required_fields)) if retriever == "compiled" else term_score
    citation_coverage = grounded_hits / max(1, len(required_fields)) if retriever == "compiled" else 0.0
    score = round((term_score * 0.55) + (field_score_value * 0.30) + (citation_coverage * 0.15), 4)
    passed = score >= 0.75 and (retriever != "compiled" or citation_coverage >= 0.99)
    return passed, score, citation_coverage


def run_eval(conn: sqlite3.Connection, suite: str, retrievers: list[str]) -> dict[str, Any]:
    if suite != SUITE_NAME:
        raise KnowledgeError(f"unknown suite: {suite}")
    init_schema(conn)
    if conn.execute("SELECT COUNT(*) AS n FROM sources").fetchone()["n"] == 0:
        ingest_sources(conn)
    if conn.execute("SELECT COUNT(*) AS n FROM artifacts").fetchone()["n"] == 0:
        compile_artifacts(conn)
    seed_eval_cases(conn)

    rows = list(conn.execute("SELECT * FROM eval_cases WHERE suite = ? ORDER BY id", (suite,)))
    summaries: dict[str, Any] = {}
    run_rows = []
    for retriever in retrievers:
        if retriever not in {"baseline", "compiled"}:
            raise KnowledgeError(f"unknown retriever: {retriever}")
        results = []
        for row in rows:
            query = json_loads(row["query_json"], {})
            expected = json_loads(row["expected_json"], {})
            started = time.perf_counter()
            result = run_compiled_query(conn, query) if retriever == "compiled" else run_baseline_query(conn, query)
            latency_ms = (time.perf_counter() - started) * 1000.0
            passed, score, citation_coverage = score_result(result, expected, retriever)
            budget = result.get("budget_used", {})
            source_bytes = int(budget.get("source_bytes_proxy", 0))
            steps = int(budget.get("steps", 1))
            run_id = stable_id(suite, retriever, row["id"], utc_now(), length=24)
            run_rows.append(
                (
                    run_id,
                    suite,
                    retriever,
                    row["id"],
                    1 if passed else 0,
                    score,
                    latency_ms,
                    source_bytes,
                    steps,
                    citation_coverage,
                    json_dumps(result),
                    utc_now(),
                )
            )
            results.append(
                {
                    "case_id": row["id"],
                    "category": row["category"],
                    "passed": passed,
                    "score": score,
                    "latency_ms": round(latency_ms, 3),
                    "source_bytes": source_bytes,
                    "steps": steps,
                    "citation_coverage": round(citation_coverage, 3),
                }
            )
        passed_count = sum(1 for item in results if item["passed"])
        latencies = sorted(item["latency_ms"] for item in results)
        byte_total = sum(item["source_bytes"] for item in results)
        summaries[retriever] = {
            "cases": len(results),
            "passed": passed_count,
            "completion_rate": round(passed_count / max(1, len(results)), 3),
            "average_score": round(sum(item["score"] for item in results) / max(1, len(results)), 4),
            "median_latency_ms": latencies[len(latencies) // 2] if latencies else 0,
            "total_source_bytes_proxy": byte_total,
            "average_steps": round(sum(item["steps"] for item in results) / max(1, len(results)), 3),
            "average_citation_coverage": round(sum(item["citation_coverage"] for item in results) / max(1, len(results)), 3),
            "results": results,
        }

    with conn:
        conn.executemany(
            """
            INSERT INTO eval_runs
              (id, suite, retriever, case_id, passed, score, latency_ms, source_bytes,
               steps, citation_coverage, answer_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            run_rows,
        )

    if "baseline" in summaries and "compiled" in summaries:
        base = max(1, summaries["baseline"]["total_source_bytes_proxy"])
        comp = max(1, summaries["compiled"]["total_source_bytes_proxy"])
        summaries["comparison"] = {
            "source_byte_reduction_x": round(base / comp, 3),
            "compiled_completion_target_met": summaries["compiled"]["completion_rate"] >= 0.9,
            "compiled_latency_target_met": summaries["compiled"]["median_latency_ms"] < 1000,
            "compiled_citation_target_met": summaries["compiled"]["average_citation_coverage"] >= 0.99,
            "compiled_source_reduction_target_met": (base / comp) >= 5,
        }
    return {"suite": suite, "retrievers": retrievers, "summary": summaries}


def load_query_file(path: Path) -> dict[str, Any]:
    return json.loads(read_text(path))


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False))


class KnowledgeSelfTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="mw_knowledge_test_"))
        self.db_path = self.temp_dir / "test.sqlite3"
        self.conn = connect(self.db_path)
        init_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        for path in sorted(self.temp_dir.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        self.temp_dir.rmdir()

    def test_schema_and_ingest(self) -> None:
        result = ingest_sources(self.conn)
        self.assertGreaterEqual(result["source_count"], 10)
        table_count = self.conn.execute("SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table'").fetchone()["n"]
        self.assertGreaterEqual(table_count, 6)

    def test_compile_and_citations(self) -> None:
        ingest_sources(self.conn)
        result = compile_artifacts(self.conn)
        self.assertGreaterEqual(result["artifact_count"], 20)
        self.assertGreaterEqual(result["citation_count"], 40)
        missing_quotes = self.conn.execute("SELECT COUNT(*) AS n FROM citations WHERE quote = ''").fetchone()["n"]
        self.assertEqual(missing_quotes, 0)

    def test_query_parser(self) -> None:
        errors = validate_query({"contexts": ["meta_project"]})
        self.assertTrue(any("ask" in error for error in errors))
        errors = validate_query(default_query("What is the project purpose?", ["meta_project"], ["purpose"]))
        self.assertEqual(errors, [])

    def test_compiled_query_contract(self) -> None:
        ingest_sources(self.conn)
        compile_artifacts(self.conn)
        result = run_compiled_query(
            self.conn,
            default_query("What are the hard boundaries?", ["meta_project"], ["hard_boundaries", "external_advice_policy"]),
        )
        self.assertIn("answer", result)
        self.assertIn("fields", result)
        self.assertIn("citations", result)
        self.assertGreaterEqual(len(result["citations"]), 2)
        self.assertFalse(any(warning.startswith("missing_citation") for warning in result["warnings"]))

    def test_acl_filter(self) -> None:
        ingest_sources(self.conn)
        compile_artifacts(self.conn)
        query = default_query("What runtime exclusions exist?", ["local_runtime_policy"], ["runtime_exclusions"])
        query["where"] = {"principal_tags": ["public"]}
        result = run_compiled_query(self.conn, query)
        self.assertTrue(result["filtered_by_acl"])
        self.assertTrue(any("context_acl_filtered" in warning for warning in result["warnings"]))

    def test_eval_scorer(self) -> None:
        ingest_sources(self.conn)
        compile_artifacts(self.conn)
        result = run_eval(self.conn, SUITE_NAME, ["compiled"])
        summary = result["summary"]["compiled"]
        self.assertGreaterEqual(summary["completion_rate"], 0.9)
        self.assertGreaterEqual(summary["average_citation_coverage"], 0.99)

    def test_sec_config_requires_user_agent(self) -> None:
        with self.assertRaises(KnowledgeError):
            load_sec_config(self.temp_dir / "missing.local.json", require_user_agent=True)

    def test_sec_normalize_helpers(self) -> None:
        raw = """
        <html><body><script>ignore()</script><h1>Item 1. Business</h1>
        <p>We employed approximately 12,345 employees.</p>
        <h1>Item 1A. Risk Factors</h1><p>Risks include supply chain issues.</p></body></html>
        """
        text = strip_sec_html(raw)
        self.assertIn("Item 1. Business", text)
        self.assertIn("12,345 employees", text)
        sections = extract_sec_sections(text)
        self.assertTrue(any(section["section_key"] == "business" for section in sections))
        self.assertTrue(any(section["section_key"] == "risk_factors" for section in sections))

    def test_sec_compile_and_eval_mock(self) -> None:
        corpus = "sec_mock"
        companies = [
            ("AAA", "0000000001", "AAA Corp", 1000, 100, 50),
            ("BBB", "0000000002", "BBB Corp", 2000, 300, 80),
            ("CCC", "0000000003", "CCC Corp", 3000, 500, 90),
        ]
        with self.conn:
            for ticker, cik, company, revenue, net_income, capex in companies:
                text_path = self.temp_dir / f"{ticker}.txt"
                facts_path = self.temp_dir / f"{ticker}.facts.json"
                text_path.write_text(
                    "\n".join(
                        [
                            "Item 1. Business",
                            f"{company} employed approximately {revenue} employees in 2022.",
                            "Item 1A. Risk Factors",
                            "Risks include competition, regulation, and supply chain disruption.",
                            "Item 7. Management Discussion and Analysis",
                            "Management discusses operating results and liquidity.",
                        ]
                    ),
                    encoding="utf-8",
                )
                facts = {
                    "facts": {
                        "us-gaap": {
                            "Revenues": {"units": {"USD": [{"fy": 2022, "fp": "FY", "form": "10-K", "val": revenue, "filed": "2023-02-01", "end": "2022-12-31", "accn": f"{cik}-23-000001"}]}},
                            "NetIncomeLoss": {"units": {"USD": [{"fy": 2022, "fp": "FY", "form": "10-K", "val": net_income, "filed": "2023-02-01", "end": "2022-12-31", "accn": f"{cik}-23-000001"}]}},
                            "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [{"fy": 2022, "fp": "FY", "form": "10-K", "val": capex, "filed": "2023-02-01", "end": "2022-12-31", "accn": f"{cik}-23-000001"}]}},
                        }
                    }
                }
                facts_path.write_text(json.dumps(facts), encoding="utf-8")
                filing_id = stable_id(corpus, ticker, "0000000000-23-000001", length=24)
                text = text_path.read_text(encoding="utf-8")
                self.conn.execute(
                    """
                    INSERT INTO sec_filings
                      (id, corpus, ticker, cik, company, form, fiscal_year, filing_date, report_date,
                       accession, primary_document, document_url, local_raw_path, local_text_path,
                       content_hash, raw_byte_count, normalized_byte_count, metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        filing_id,
                        corpus,
                        ticker,
                        cik,
                        company,
                        "10-K",
                        2022,
                        "2023-02-01",
                        "2022-12-31",
                        "0000000000-23-000001",
                        f"{ticker}.htm",
                        f"https://www.sec.gov/mock/{ticker}",
                        str(text_path),
                        str(text_path),
                        sha256_text(text),
                        len(text.encode("utf-8")),
                        len(text.encode("utf-8")),
                        json_dumps({"local_companyfacts_path": str(facts_path)}),
                        utc_now(),
                    ),
                )
                for section in extract_sec_sections(text):
                    self.conn.execute(
                        """
                        INSERT INTO sec_sections (id, filing_id, section_key, heading, line_start, line_end, text_preview)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            stable_id(filing_id, section["section_key"], length=24),
                            filing_id,
                            section["section_key"],
                            section["heading"],
                            section["line_start"],
                            section["line_end"],
                            section["text_preview"],
                        ),
                    )
        sec_compile(argparse.Namespace(db=str(self.db_path), corpus=corpus))
        artifact_count = self.conn.execute("SELECT COUNT(*) AS n FROM sec_artifacts WHERE corpus = ?", (corpus,)).fetchone()["n"]
        self.assertEqual(artifact_count, 3)
        result = run_sec_eval(self.conn, SEC_SUITE_NAME, ["compiled"], corpus, limit=6)
        self.assertGreaterEqual(result["summary"]["compiled"]["completion_rate"], 0.9)


def run_self_tests() -> dict[str, Any]:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(KnowledgeSelfTests)
    stream = _JsonTestStream()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)
    result = runner.run(suite)
    return {
        "status": "passed" if result.wasSuccessful() else "failed",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "details": stream.lines,
    }


class _JsonTestStream:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, value: str) -> None:
        clean = value.strip()
        if clean:
            self.lines.append(clean)

    def flush(self) -> None:
        return None


def command_ingest(args: argparse.Namespace) -> dict[str, Any]:
    with connect(Path(args.db)) as conn:
        result = ingest_sources(conn)
        result["db_path"] = str(Path(args.db))
        return result


def command_compile(args: argparse.Namespace) -> dict[str, Any]:
    with connect(Path(args.db)) as conn:
        return compile_artifacts(conn)


def command_query(args: argparse.Namespace) -> dict[str, Any]:
    with connect(Path(args.db)) as conn:
        query = load_query_file(Path(args.file))
        return run_compiled_query(conn, query)


def command_eval(args: argparse.Namespace) -> dict[str, Any]:
    retrievers = [item.strip() for item in args.compare.split(",") if item.strip()]
    with connect(Path(args.db)) as conn:
        return run_eval(conn, args.suite, retrievers)


def normalize_ikun_retrievers(value: str) -> list[str]:
    aliases = {
        "coding-agent": "coding_sandbox",
        "coding_agent": "coding_sandbox",
        "coding-sandbox": "coding_sandbox",
        "coding_sandbox": "coding_sandbox",
        "agentic-rag": "agentic_rag",
        "agentic_rag": "agentic_rag",
        "compiled-artifacts": "compiled",
        "compiled_artifacts": "compiled",
        "compiled": "compiled",
    }
    retrievers = []
    for item in value.split(","):
        key = item.strip()
        if not key:
            continue
        normalized = aliases.get(key)
        if not normalized:
            raise KnowledgeError(f"unknown ikun retriever: {key}")
        retrievers.append(normalized)
    return retrievers


def command_ikun_ingest(args: argparse.Namespace) -> dict[str, Any]:
    return ikun_ingest(args)


def command_ikun_compile(args: argparse.Namespace) -> dict[str, Any]:
    return ikun_compile(args)


def command_ikun_query(args: argparse.Namespace) -> dict[str, Any]:
    with connect(Path(args.db)) as conn:
        query = load_query_file(Path(args.file))
        return run_ikun_compiled_query(conn, query, args.corpus)


def command_ikun_eval(args: argparse.Namespace) -> dict[str, Any]:
    retrievers = normalize_ikun_retrievers(args.compare)
    with connect(Path(args.db)) as conn:
        result = run_ikun_eval(conn, args.suite, retrievers, args.corpus, args.limit)
    result["analysis_outputs"] = write_ikun_analysis_outputs(args.corpus, result)
    return result


def command_ikun_agent_pack(args: argparse.Namespace) -> dict[str, Any]:
    return ikun_agent_pack(args)


def command_ikun_agent_import(args: argparse.Namespace) -> dict[str, Any]:
    return ikun_agent_import(args)


def command_ikun_judge_pack(args: argparse.Namespace) -> dict[str, Any]:
    if not getattr(args, "blind", False):
        args.blind = True
    return ikun_blind_judge_pack(args)


def command_ikun_judge_import(args: argparse.Namespace) -> dict[str, Any]:
    return ikun_judge_import(args)


def command_ikun_analysis(args: argparse.Namespace) -> dict[str, Any]:
    return ikun_analysis(args)


def normalize_sec_retrievers(value: str) -> list[str]:
    aliases = {
        "coding-agent": "coding_agent",
        "coding_agent": "coding_agent",
        "coding-sandbox": "coding_sandbox",
        "coding_sandbox": "coding_sandbox",
        "agentic-rag": "agentic_rag",
        "agentic_rag": "agentic_rag",
        "compiled-artifacts": "compiled",
        "compiled_artifacts": "compiled",
        "compiled": "compiled",
    }
    retrievers = []
    for item in value.split(","):
        key = item.strip()
        if not key:
            continue
        normalized = aliases.get(key)
        if not normalized:
            raise KnowledgeError(f"unknown SEC retriever: {key}")
        retrievers.append(normalized)
    return retrievers


def command_sec_download(args: argparse.Namespace) -> dict[str, Any]:
    try:
        return sec_download(args)
    except KnowledgeError as exc:
        if getattr(args, "audit", False):
            audit = write_blocked_sec_audit(args.corpus, str(exc), int(args.max_filings or 493))
            return {"status": "blocked_official_download", "corpus": args.corpus, "error": str(exc), "manifest_audit_path": str(sec_paths(args.corpus)["manifest_audit"]), "audit": audit}
        raise


def command_sec_manifest_build(args: argparse.Namespace) -> dict[str, Any]:
    return sec_manifest_build(args)


def command_sec_import_hf(args: argparse.Namespace) -> dict[str, Any]:
    return sec_import_hf(args)


def command_sec_normalize(args: argparse.Namespace) -> dict[str, Any]:
    return sec_normalize(args)


def command_sec_compile(args: argparse.Namespace) -> dict[str, Any]:
    return sec_compile(args)


def command_sec_eval(args: argparse.Namespace) -> dict[str, Any]:
    retrievers = normalize_sec_retrievers(args.compare)
    with connect(Path(args.db)) as conn:
        result = run_sec_eval(conn, args.suite, retrievers, args.corpus, args.limit)
    result["analysis_outputs"] = write_sec_analysis_outputs(args.corpus, result)
    return result


def command_sec_judge_pack(args: argparse.Namespace) -> dict[str, Any]:
    return sec_judge_pack(args)


def command_sec_groundtruth_build(args: argparse.Namespace) -> dict[str, Any]:
    return sec_groundtruth_build(args)


def command_sec_agent_pack(args: argparse.Namespace) -> dict[str, Any]:
    return sec_agent_pack(args)


def command_sec_agent_import(args: argparse.Namespace) -> dict[str, Any]:
    return sec_agent_import(args)


def command_sec_judge_import(args: argparse.Namespace) -> dict[str, Any]:
    return sec_judge_import(args)


def command_sec_analysis(args: argparse.Namespace) -> dict[str, Any]:
    return sec_analysis(args)


def command_self_test(args: argparse.Namespace) -> dict[str, Any]:
    return run_self_tests()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Meta_workflow Nexus-like knowledge compiler")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Ingest repository source documents")
    ingest.set_defaults(func=command_ingest)

    compile_cmd = sub.add_parser("compile", help="Compile sources into typed artifacts")
    compile_cmd.set_defaults(func=command_compile)

    query = sub.add_parser("query", help="Run a KnowQL-like JSON query")
    query.add_argument("--file", required=True, help="Path to query JSON")
    query.set_defaults(func=command_query)

    eval_cmd = sub.add_parser("eval", help="Run a retrieval benchmark")
    eval_cmd.add_argument("--suite", default=SUITE_NAME)
    eval_cmd.add_argument("--compare", default="baseline,compiled")
    eval_cmd.set_defaults(func=command_eval)

    ikun_ingest_cmd = sub.add_parser("ikun-ingest", help="Ingest a read-only external ikunAim text corpus")
    ikun_ingest_cmd.add_argument("--root", default=str(IKUN_DEFAULT_ROOT))
    ikun_ingest_cmd.add_argument("--corpus", default=IKUN_CORPUS_ID)
    ikun_ingest_cmd.add_argument("--scope", default="full-readable")
    ikun_ingest_cmd.add_argument("--max-sources", type=int, default=0)
    ikun_ingest_cmd.set_defaults(func=command_ikun_ingest)

    ikun_compile_cmd = sub.add_parser("ikun-compile", help="Compile ikunAim sources into typed artifacts")
    ikun_compile_cmd.add_argument("--corpus", default=IKUN_CORPUS_ID)
    ikun_compile_cmd.set_defaults(func=command_ikun_compile)

    ikun_query_cmd = sub.add_parser("ikun-query", help="Run a KnowQL-like ikunAim query")
    ikun_query_cmd.add_argument("--corpus", default=IKUN_CORPUS_ID)
    ikun_query_cmd.add_argument("--file", required=True)
    ikun_query_cmd.set_defaults(func=command_ikun_query)

    ikun_eval_cmd = sub.add_parser("ikun-eval", help="Run ikunAim Nexus-like benchmark")
    ikun_eval_cmd.add_argument("--suite", default=IKUN_SUITE_NAME)
    ikun_eval_cmd.add_argument("--corpus", default=IKUN_CORPUS_ID)
    ikun_eval_cmd.add_argument("--compare", default="coding_sandbox,agentic_rag,compiled")
    ikun_eval_cmd.add_argument("--limit", type=int, default=90)
    ikun_eval_cmd.set_defaults(func=command_ikun_eval)

    ikun_agent_pack_cmd = sub.add_parser("ikun-agent-pack", help="Export ikunAim retrieval evidence packs for Codex composer")
    ikun_agent_pack_cmd.add_argument("--suite", default=IKUN_SUITE_NAME)
    ikun_agent_pack_cmd.add_argument("--corpus", default=IKUN_CORPUS_ID)
    ikun_agent_pack_cmd.add_argument("--retriever", default="coding_sandbox,agentic_rag,compiled")
    ikun_agent_pack_cmd.add_argument("--composer", default="codex")
    ikun_agent_pack_cmd.add_argument("--limit", type=int, default=90)
    ikun_agent_pack_cmd.set_defaults(func=command_ikun_agent_pack)

    ikun_agent_import_cmd = sub.add_parser("ikun-agent-import", help="Import Codex-composed ikunAim agent answers")
    ikun_agent_import_cmd.add_argument("--suite", default=IKUN_SUITE_NAME)
    ikun_agent_import_cmd.add_argument("--corpus", default=IKUN_CORPUS_ID)
    ikun_agent_import_cmd.add_argument("--input", required=True)
    ikun_agent_import_cmd.set_defaults(func=command_ikun_agent_import)

    ikun_judge_cmd = sub.add_parser("ikun-judge-pack", help="Export blinded ikunAim judge pack JSONL")
    ikun_judge_cmd.add_argument("--suite", default=IKUN_SUITE_NAME)
    ikun_judge_cmd.add_argument("--corpus", default=IKUN_CORPUS_ID)
    ikun_judge_cmd.add_argument("--limit", type=int, default=90)
    ikun_judge_cmd.add_argument("--output", default="")
    ikun_judge_cmd.add_argument("--blind", action="store_true")
    ikun_judge_cmd.add_argument("--judge", default="codex")
    ikun_judge_cmd.set_defaults(func=command_ikun_judge_pack)

    ikun_judge_import_cmd = sub.add_parser("ikun-judge-import", help="Import blinded Codex judge results for ikunAim")
    ikun_judge_import_cmd.add_argument("--suite", default=IKUN_SUITE_NAME)
    ikun_judge_import_cmd.add_argument("--corpus", default=IKUN_CORPUS_ID)
    ikun_judge_import_cmd.add_argument("--input", required=True)
    ikun_judge_import_cmd.add_argument("--judge", default="codex")
    ikun_judge_import_cmd.set_defaults(func=command_ikun_judge_import)

    ikun_analysis_cmd = sub.add_parser("ikun-analysis", help="Write ikunAim comparison and judge analysis")
    ikun_analysis_cmd.add_argument("--suite", default=IKUN_SUITE_NAME)
    ikun_analysis_cmd.add_argument("--corpus", default=IKUN_CORPUS_ID)
    ikun_analysis_cmd.add_argument("--compare", default="coding_sandbox,agentic_rag,compiled")
    ikun_analysis_cmd.add_argument("--limit", type=int, default=90)
    ikun_analysis_cmd.set_defaults(func=command_ikun_analysis)

    sec_manifest_cmd = sub.add_parser("sec-manifest-build", help="Build a public S&P 500-style SEC ticker manifest")
    sec_manifest_cmd.add_argument("--corpus", default=KRAFT_PUBLIC_CORPUS_ID)
    sec_manifest_cmd.add_argument("--as-of", default="2022-12-31")
    sec_manifest_cmd.add_argument("--target-filings", type=int, default=493)
    sec_manifest_cmd.add_argument("--manifest-file", default="")
    sec_manifest_cmd.add_argument("--manifest-url", default="")
    sec_manifest_cmd.set_defaults(func=command_sec_manifest_build)

    sec_download_cmd = sub.add_parser("sec-download", help="Download SEC 2022 10-K corpus files")
    sec_download_cmd.add_argument("--config", default=str(SEC_CONFIG_LOCAL), help="Local SEC config path")
    sec_download_cmd.add_argument("--corpus", default=SEC_CORPUS_ID)
    sec_download_cmd.add_argument("--max-filings", type=int, default=None)
    sec_download_cmd.add_argument("--resume", action="store_true", help="Skip files that already exist")
    sec_download_cmd.add_argument("--audit", action="store_true", help="Write manifest_audit.json even when official download is blocked")
    sec_download_cmd.add_argument("--refresh", action="store_true", help="Re-download existing SEC metadata and filings")
    sec_download_cmd.set_defaults(func=command_sec_download)

    sec_import_hf_cmd = sub.add_parser("sec-import-hf", help="Import downloaded Hugging Face SEC 10-K JSONL shards")
    sec_import_hf_cmd.add_argument("--corpus", default=HF_SEC_CORPUS_ID)
    sec_import_hf_cmd.add_argument("--source-dir", default="")
    sec_import_hf_cmd.add_argument("--target-min-mb", type=float, default=245)
    sec_import_hf_cmd.add_argument("--target-max-mb", type=float, default=260)
    sec_import_hf_cmd.add_argument("--max-filings", type=int, default=0)
    sec_import_hf_cmd.set_defaults(func=command_sec_import_hf)

    sec_normalize_cmd = sub.add_parser("sec-normalize", help="Normalize downloaded SEC HTML/SGML filings")
    sec_normalize_cmd.add_argument("--corpus", default=SEC_CORPUS_ID)
    sec_normalize_cmd.add_argument("--target-mb", type=int, default=250)
    sec_normalize_cmd.set_defaults(func=command_sec_normalize)

    sec_compile_cmd = sub.add_parser("sec-compile", help="Compile SEC filings into company fact sheet artifacts")
    sec_compile_cmd.add_argument("--corpus", default=SEC_CORPUS_ID)
    sec_compile_cmd.set_defaults(func=command_sec_compile)

    sec_eval_cmd = sub.add_parser("sec-eval", help="Run SEC 10-K benchmark")
    sec_eval_cmd.add_argument("--suite", default=SEC_SUITE_NAME)
    sec_eval_cmd.add_argument("--corpus", default=SEC_CORPUS_ID)
    sec_eval_cmd.add_argument("--compare", default="coding_sandbox,agentic_rag,compiled")
    sec_eval_cmd.add_argument("--limit", type=int, default=150)
    sec_eval_cmd.set_defaults(func=command_sec_eval)

    sec_groundtruth_cmd = sub.add_parser("sec-groundtruth-build", help="Build locked independent SEC ground truth JSONL")
    sec_groundtruth_cmd.add_argument("--suite", default=KRAFT_PUBLIC_SUITE_NAME)
    sec_groundtruth_cmd.add_argument("--corpus", default=KRAFT_PUBLIC_CORPUS_ID)
    sec_groundtruth_cmd.add_argument("--limit", type=int, default=150)
    sec_groundtruth_cmd.add_argument("--lock", action="store_true")
    sec_groundtruth_cmd.add_argument("--force", action="store_true")
    sec_groundtruth_cmd.set_defaults(func=command_sec_groundtruth_build)

    sec_agent_pack_cmd = sub.add_parser("sec-agent-pack", help="Export retrieval evidence packs for Codex composer")
    sec_agent_pack_cmd.add_argument("--suite", default=KRAFT_PUBLIC_SUITE_NAME)
    sec_agent_pack_cmd.add_argument("--corpus", default=KRAFT_PUBLIC_CORPUS_ID)
    sec_agent_pack_cmd.add_argument("--retriever", default="coding_agent,agentic_rag,compiled")
    sec_agent_pack_cmd.add_argument("--composer", default="codex")
    sec_agent_pack_cmd.add_argument("--budget-seconds", type=int, default=120)
    sec_agent_pack_cmd.add_argument("--token-budget", type=int, default=1_000_000)
    sec_agent_pack_cmd.add_argument("--limit", type=int, default=150)
    sec_agent_pack_cmd.set_defaults(func=command_sec_agent_pack)

    sec_agent_import_cmd = sub.add_parser("sec-agent-import", help="Import Codex-composed SEC agent answers")
    sec_agent_import_cmd.add_argument("--suite", default=KRAFT_PUBLIC_SUITE_NAME)
    sec_agent_import_cmd.add_argument("--corpus", default=KRAFT_PUBLIC_CORPUS_ID)
    sec_agent_import_cmd.add_argument("--input", required=True)
    sec_agent_import_cmd.set_defaults(func=command_sec_agent_import)

    sec_judge_cmd = sub.add_parser("sec-judge-pack", help="Export SEC LLM judge pack JSONL")
    sec_judge_cmd.add_argument("--suite", default=SEC_SUITE_NAME)
    sec_judge_cmd.add_argument("--corpus", default=SEC_CORPUS_ID)
    sec_judge_cmd.add_argument("--compare", default="coding_sandbox,agentic_rag,compiled")
    sec_judge_cmd.add_argument("--limit", type=int, default=150)
    sec_judge_cmd.add_argument("--output", default="")
    sec_judge_cmd.add_argument("--blind", action="store_true")
    sec_judge_cmd.add_argument("--judge", default="codex")
    sec_judge_cmd.set_defaults(func=command_sec_judge_pack)

    sec_judge_import_cmd = sub.add_parser("sec-judge-import", help="Import blinded Codex judge results")
    sec_judge_import_cmd.add_argument("--suite", default=KRAFT_PUBLIC_SUITE_NAME)
    sec_judge_import_cmd.add_argument("--corpus", default=KRAFT_PUBLIC_CORPUS_ID)
    sec_judge_import_cmd.add_argument("--input", required=True)
    sec_judge_import_cmd.add_argument("--judge", default="codex")
    sec_judge_import_cmd.set_defaults(func=command_sec_judge_import)

    sec_analysis_cmd = sub.add_parser("sec-analysis", help="Write KRAFT-style official delta analysis")
    sec_analysis_cmd.add_argument("--suite", default=KRAFT_PUBLIC_SUITE_NAME)
    sec_analysis_cmd.add_argument("--corpus", default=KRAFT_PUBLIC_CORPUS_ID)
    sec_analysis_cmd.add_argument("--compare-official-pinecone", action="store_true")
    sec_analysis_cmd.set_defaults(func=command_sec_analysis)

    self_test = sub.add_parser("self-test", help="Run built-in tests")
    self_test.set_defaults(func=command_self_test)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
        print_json(result)
        if result.get("status") == "failed":
            return 1
        return 0
    except KnowledgeError as exc:
        print_json({"status": "failed", "error": str(exc)})
        return 2
    except json.JSONDecodeError as exc:
        print_json({"status": "failed", "error": f"invalid JSON: {exc}"})
        return 2
    except BrokenPipeError:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
