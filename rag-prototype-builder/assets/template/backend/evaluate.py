"""Evaluation: run the golden questions, score them, save the run, compare with the previous run.

data/questions.jsonl, one object per line:
  {"id": "q1", "question": "...", "answerable": true, "user_id": "admin",
   "expected_sources": ["returns.md"],          # substrings of chunk ids
   "expected_answer": "30 days"}                # optional, used by --judge
"""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from .generate import parse_output
from .pipeline import RAG

RUNS_DIR = Path("eval_runs")
JUDGE_SYSTEM = """You grade a RAG system's answer against an expected answer.
Return only JSON: {"correct": true|false, "why": "<one sentence>"}.
Correct means the answer states the same key facts as the expected answer and adds nothing that contradicts it."""


def _matches(chunk_id: str, expected: list[str]) -> bool:
    return any(e.lower() in chunk_id.lower() for e in expected)


def score_item(item: dict, r: dict) -> dict:
    expected = item.get("expected_sources", [])
    answerable = item.get("answerable", True)
    ids = [x["chunk_id"] for x in r["retrieved"]]
    first = next((i for i, cid in enumerate(ids, 1) if _matches(cid, expected)), None)
    return {
        "id": item.get("id"),
        "question": item["question"],
        "user_id": r["user_id"],
        "answerable": answerable,
        "abstained": r["abstained"],
        "reason": r["reason"],
        "answer": r["answer"],
        "hit": (first is not None) if answerable else None,
        "rr": (1 / first if first else 0.0) if answerable else None,
        "cited_expected": any(_matches(c["chunk_id"], expected) for c in r["citations"]) if answerable else None,
        "latency_ms": sum(r["timings"].values()),
    }


def summarize(rows: list[dict]) -> dict:
    ans = [r for r in rows if r["answerable"]]
    unans = [r for r in rows if not r["answerable"]]
    abstained = [r for r in rows if r["abstained"]]
    judged = [r["judge_correct"] for r in rows if r.get("judge_correct") is not None]
    lat = sorted(r["latency_ms"] for r in rows)

    def rate(xs):
        return round(sum(xs) / len(xs), 3) if xs else None

    return {
        "n": len(rows),
        "n_answerable": len(ans),
        "hit@k": rate([r["hit"] for r in ans]),
        "mrr": rate([r["rr"] for r in ans]),
        "citation_hit": rate([r["cited_expected"] for r in ans]),
        "abstain_recall": rate([r["abstained"] for r in unans]),
        "abstain_precision": rate([not r["answerable"] for r in abstained]),
        "judge_accuracy": rate(judged),
        "latency_p50_ms": round(statistics.median(lat), 1) if lat else None,
    }


def run(questions_path: str, judge: bool = False, label: str = "") -> dict:
    items = [json.loads(l) for l in Path(questions_path).read_text().splitlines() if l.strip()]
    rag = RAG()
    rows = []
    for item in items:
        row = score_item(item, rag.ask(item["question"], item.get("user_id", "admin")))
        if judge and item.get("expected_answer") and row["answerable"] and not row["abstained"]:
            prompt = f"Question: {item['question']}\nExpected: {item['expected_answer']}\nSystem: {row['answer']}"
            verdict = parse_output(rag.llm.complete(JUDGE_SYSTEM, prompt))
            if verdict is None:
                raise RuntimeError(f"judge returned unparseable output for {item.get('id')}")
            row["judge_correct"] = bool(verdict.get("correct"))
        rows.append(row)

    summary = summarize(rows)
    previous = sorted(RUNS_DIR.glob("*.json"))
    prev = json.loads(previous[-1].read_text())["summary"] if previous else {}
    RUNS_DIR.mkdir(exist_ok=True)
    path = RUNS_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}{'-' + label if label else ''}.json"
    path.write_text(json.dumps({"label": label, "llm": rag.llm.name, "embedder": rag.embedder.name,
                                "summary": summary, "rows": rows}, indent=2))

    stub = "  (TEST STUB LLM: scores are not quality)" if rag.llm.provider == "offline" else ""
    print(f"\nEval {questions_path} with {rag.llm.name}, {rag.embedder.name}{stub}\nSaved {path}")
    print(f"{'metric':<20}{'value':>8}{'prev':>8}{'delta':>8}")
    for key, val in summary.items():
        p = prev.get(key)
        delta = f"{val - p:+.3f}" if isinstance(val, (int, float)) and isinstance(p, (int, float)) else ""
        print(f"{key:<20}{str(val):>8}{str('' if p is None else p):>8}{delta:>8}")

    fails = [r for r in rows if (r["answerable"] and (not r["hit"] or r["abstained"] or not r["cited_expected"]))
             or (not r["answerable"] and not r["abstained"]) or r.get("judge_correct") is False]
    for r in fails:
        kind = ("retrieval miss" if r["answerable"] and not r["hit"] else
                "wrongly abstained" if r["answerable"] and r["abstained"] else
                "cited wrong source" if r["answerable"] and not r["cited_expected"] else
                "answered unanswerable" if not r["answerable"] else "judge: incorrect")
        print(f"  FAIL {r['id']}: {kind} | {r['question'][:60]}")
    print(f"{summary['n']} items: one item = {100 / max(summary['n'], 1):.0f} points on a rate.")
    return summary
