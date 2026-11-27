"""Regression: golden-set metrics must not drop below a saved baseline.

Runs offline (stub LLM + keyword search), so it is deterministic and free.
- hit@k and mrr measure retrieval: these are real regression signals.
- citation/abstention metrics run through the stub model, so they catch changes to the
  guard, gate and prompt plumbing, not answer quality. Quality needs ./ci.sh --live.

Two gates:
1. tests/fixtures (always runs): the plumbing works on fixed data.
2. data/ (the owner's documents, users and questions): runs once data/questions.jsonl has items.
   The first run saves tests/data_baseline.json; after that, a drop fails CI.

Improved a metric on purpose, or changed the question set? Update the baselines:
    UPDATE_BASELINE=1 .venv/bin/python -m pytest tests/test_regression.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATED = ["hit@k", "mrr", "citation_hit", "abstain_recall", "abstain_precision"]


def _check(summary: dict, baseline_path: Path) -> None:
    if os.getenv("UPDATE_BASELINE") == "1" or not baseline_path.exists():
        comment = (json.loads(baseline_path.read_text()).get("_comment", "") if baseline_path.exists()
                   else "Offline stub + keyword search. Update only on purpose (see tests/test_regression.py).")
        new = {"_comment": comment, "n": summary["n"], **{k: summary[k] for k in GATED}}
        baseline_path.write_text(json.dumps(new, indent=2) + "\n")
        if os.getenv("UPDATE_BASELINE") != "1":
            pytest.skip(f"no baseline yet: saved the first one to tests/{baseline_path.name}; commit it")
        return
    baseline = json.loads(baseline_path.read_text())
    assert summary["n"] == baseline["n"], "question set changed: review it, then update the baseline on purpose"
    drops = {k: (baseline[k], summary[k]) for k in GATED
             if summary[k] is not None and baseline.get(k) is not None and summary[k] < baseline[k]}
    assert not drops, f"metrics dropped below baseline (baseline, now): {drops}"


def test_fixture_metrics_do_not_regress(rag, tmp_path, monkeypatch):
    from backend.evaluate import run

    monkeypatch.chdir(tmp_path)
    summary = run(str(ROOT / "tests" / "fixtures" / "questions.jsonl"), label="regression")
    _check(summary, ROOT / "tests" / "regression_baseline.json")


def test_owner_data_metrics_do_not_regress(tmp_path, monkeypatch):
    questions = ROOT / "data" / "questions.jsonl"
    if not questions.exists() or not questions.read_text().strip():
        pytest.skip("data/questions.jsonl is empty: add golden questions for your own documents (milestone M3)")
    monkeypatch.setenv("LLM_PROVIDER", "offline")
    monkeypatch.setenv("EMBED_PROVIDER", "none")
    monkeypatch.setenv("DATA_DIR", str(ROOT / "data" / "sample"))
    monkeypatch.setenv("USERS_FILE", str(ROOT / "data" / "users.json"))
    monkeypatch.setenv("INDEX_DIR", str(tmp_path / "index"))
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    from backend.evaluate import run
    from backend.pipeline import RAG

    RAG().ingest()
    monkeypatch.chdir(tmp_path)
    summary = run(str(questions), label="regression-data")
    _check(summary, ROOT / "tests" / "data_baseline.json")
