#!/usr/bin/env python3
"""Triggering tests (guide, chapter 3): does the skill load on relevant requests and stay quiet otherwise?

Runs each query from evals/triggers.json through headless Claude Code (`claude -p`) in a temp
project that has only this skill installed in .claude/skills/. Tools that change anything are
disallowed, and each run stops after its first turns, so a query only reveals whether the Skill
tool was invoked. Uses your Claude Code login; roughly one short request per query.

Usage: python evals/run_trigger_tests.py [--max-turns 2]
Writes evals/results/triggers-YYYYMMDD-HHMM.json and prints a summary.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "rag-prototype-builder"


def invoked(query: str, cwd: Path, max_turns: int, name: str) -> tuple[bool, str]:
    cmd = ["claude", "-p", query, "--output-format", "stream-json", "--verbose",
           "--max-turns", str(max_turns),
           "--strict-mcp-config",  # no MCP connectors, so a test query can't reach outside services
           "--disallowedTools", "Bash,Write,Edit,NotebookEdit,WebFetch,WebSearch,Agent,Artifact,ArtifactData,ArtifactComments"]
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=240).stdout
    except subprocess.TimeoutExpired:
        return False, "timeout"
    first_tools: list[str] = []
    for line in out.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = ev.get("message") if isinstance(ev, dict) else None
        content = msg.get("content") if isinstance(msg, dict) else None
        for block in content if isinstance(content, list) else []:
            if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") != "Skill":
                first_tools.append(block.get("name"))
            if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Skill":
                skill = str((block.get("input") or {}).get("skill", ""))
                if skill.split(":")[-1] == name:
                    return True, skill
                return False, f"other skill: {skill}"
    return False, "no skill" + (f"; used {first_tools[:3]}" if first_tools else "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-turns", type=int, default=2)
    args = ap.parse_args()
    if not shutil.which("claude"):
        raise SystemExit("claude CLI not found: install Claude Code to run triggering tests")
    spec = json.loads((ROOT / "evals" / "triggers.json").read_text())
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        proj = Path(tmp)
        shutil.copytree(SKILL, proj / ".claude" / "skills" / SKILL.name)
        for group, expect in [("should_trigger", True), ("paraphrased_should_trigger", True), ("should_not_trigger", False)]:
            for q in spec[group]:
                got, detail = invoked(q, proj, args.max_turns, spec["skill"])
                ok = got == expect
                rows.append({"group": group, "query": q, "expected": expect, "triggered": got, "ok": ok, "detail": detail})
                print(f"{'PASS' if ok else 'FAIL'}  [{group}] triggered={got} ({detail})  {q}", flush=True)
    summary = {}
    for g in ["should_trigger", "paraphrased_should_trigger", "should_not_trigger"]:
        rs = [r for r in rows if r["group"] == g]
        summary[g] = f"{sum(r['ok'] for r in rs)}/{len(rs)}"
    relevant = [r for r in rows if r["expected"]]
    summary["trigger_rate_relevant"] = round(sum(r["triggered"] for r in relevant) / len(relevant), 3)
    print("\nSummary:", json.dumps(summary))
    out = ROOT / "evals" / "results" / f"triggers-{time.strftime('%Y%m%d-%H%M')}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    print(f"Saved {out.relative_to(ROOT)}")
    return 0 if all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
