"""Regression: the golden-set metrics must not drop below the saved baseline.

Runs offline (stub LLM + keyword search), so it is deterministic and free.
- hit@k and mrr measure retrieval: these are real regression signals.
- citation/abstention metrics run through the stub model, so they catch changes to the
  guard, gate and prompt plumbing, not answer quality. Quality needs a live eval (see TEST.md).

Improved a metric on purpose? Update the baseline:
    UPDATE_BASELINE=1 .venv/bin/python -m pytest tests/test_regression.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = Path(__file__).with_name("regression_baseline.json")
GATED = ["hit@k", "mrr", "citation_hit", "abstain_recall", "abstain_precision"]


def test_metrics_do_not_regress(rag, tmp_path, monkeypatch):
    from backend.evaluate import run

    monkeypatch.chdir(tmp_path)
    summary = run(str(ROOT / "data" / "questions.jsonl"), label="regression")
    baseline = json.loads(BASELINE.read_text())

    if os.getenv("UPDATE_BASELINE") == "1":
        new = {"_comment": baseline["_comment"], "n": summary["n"], **{k: summary[k] for k in GATED}}
        BASELINE.write_text(json.dumps(new, indent=2) + "\n")
        return

    assert summary["n"] == baseline["n"], "question set changed: review it, then update the baseline on purpose"
    drops = {k: (baseline[k], summary[k]) for k in GATED if summary[k] is not None and summary[k] < baseline[k]}
    assert not drops, f"metrics dropped below baseline (baseline, now): {drops}"
