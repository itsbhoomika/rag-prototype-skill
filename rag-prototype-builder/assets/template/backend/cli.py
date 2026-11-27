"""Command line.

    python -m backend.cli doctor [--require-real]        # check providers and keys
    python -m backend.cli ingest [data_dir]              # build the index
    python -m backend.cli ask "question" --user alice    # ask as a user
    python -m backend.cli eval [--judge] [--label name] [--strict]
                                                         # run data/questions.jsonl; --strict exits 1
                                                         # if any item fails or the set is empty
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from .config import Settings
from .providers import LLM, REQUIRED_ENV, Embedder


def doctor(require_real: bool = False) -> int:
    s = Settings.from_env()
    print(f"LLM_PROVIDER={s.llm_provider}  EMBED_PROVIDER={s.embed_provider}")
    if s.llm_provider == "offline":
        print("  WARNING: offline is a test stub, not a real model.")
        if require_real:
            print("FAILED: a live check needs a real model. Set LLM_PROVIDER and its key in .env.")
            return 1
    for name in sorted({k for v in REQUIRED_ENV.values() for k in v}):
        print(f"  {name}: {'set' if os.getenv(name) else 'not set'}")  # never print values
    ok = True
    try:
        llm = LLM(s)
        t = time.perf_counter()
        out = llm.complete("Reply with the single word OK.", "Question: ping")
        print(f"LLM  {llm.name}: OK in {time.perf_counter() - t:.1f}s -> {out.strip()[:60]!r}")
    except Exception as e:  # noqa: BLE001 - doctor reports every failure
        ok = False
        print(f"LLM  FAILED: {type(e).__name__}: {e}")
    emb = Embedder(s)
    if emb.enabled:
        try:
            t = time.perf_counter()
            print(f"EMB  {emb.name}: OK in {time.perf_counter() - t:.1f}s, dim={emb.embed(['hello']).shape[1]}")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"EMB  FAILED: {type(e).__name__}: {e}")
    else:
        print("EMB  none: keyword (BM25) search only")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m backend.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    pd = sub.add_parser("doctor")
    pd.add_argument("--require-real", action="store_true", help="fail if LLM_PROVIDER is the offline stub")
    pi = sub.add_parser("ingest")
    pi.add_argument("data_dir", nargs="?")
    pa = sub.add_parser("ask")
    pa.add_argument("question")
    pa.add_argument("--user", required=True, help="user id from data/users.json")
    pe = sub.add_parser("eval")
    pe.add_argument("questions", nargs="?", default="data/questions.jsonl")
    pe.add_argument("--judge", action="store_true")
    pe.add_argument("--label", default="")
    pe.add_argument("--strict", action="store_true", help="exit 1 if any item fails or there are no items")
    args = p.parse_args(argv)

    if args.cmd == "doctor":
        return doctor(args.require_real)

    from .pipeline import RAG

    if args.cmd == "ingest":
        print(json.dumps(RAG().ingest(args.data_dir), indent=2))
    elif args.cmd == "ask":
        r = RAG().ask(args.question, args.user)
        print(f"\nABSTAINED: {r['reason']}" if r["abstained"] else f"\n{r['answer']}")
        for c in r["citations"]:
            print(f"  [{c['label']}] {c['source']}" + (f" > {c['section']}" if c["section"] else ""))
        for w in r["warnings"]:
            print(f"  warning: {w}")
        print(f"  ({r['llm']}{' TEST STUB' if r['llm_is_test_stub'] else ''}, {r['timings']})")
    elif args.cmd == "eval":
        from .evaluate import run

        summary = run(args.questions, judge=args.judge, label=args.label)
        if args.strict and (summary["n"] == 0 or summary["n_failed"] > 0):
            why = "no golden questions" if summary["n"] == 0 else f"{summary['n_failed']} of {summary['n']} items failed"
            print(f"STRICT EVAL FAILED: {why}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
