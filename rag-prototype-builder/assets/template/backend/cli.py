"""Command line.

    python -m backend.cli doctor                         # check providers and keys
    python -m backend.cli ingest [data_dir]              # build the index
    python -m backend.cli ask "question" --user alice    # ask as a user
    python -m backend.cli eval [--judge] [--label name]  # run data/questions.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from .config import Settings
from .providers import LLM, REQUIRED_ENV, Embedder


def doctor() -> int:
    s = Settings.from_env()
    print(f"LLM_PROVIDER={s.llm_provider}  EMBED_PROVIDER={s.embed_provider}")
    if s.llm_provider == "offline":
        print("  WARNING: offline is a test stub, not a real model.")
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
    sub.add_parser("doctor")
    pi = sub.add_parser("ingest")
    pi.add_argument("data_dir", nargs="?")
    pa = sub.add_parser("ask")
    pa.add_argument("question")
    pa.add_argument("--user", required=True, help="user id from data/users.json")
    pe = sub.add_parser("eval")
    pe.add_argument("questions", nargs="?", default="data/questions.jsonl")
    pe.add_argument("--judge", action="store_true")
    pe.add_argument("--label", default="")
    args = p.parse_args(argv)

    if args.cmd == "doctor":
        return doctor()

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

        run(args.questions, judge=args.judge, label=args.label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
