#!/usr/bin/env python3
"""Deterministic checks for the non-negotiable RAG rules. Code is checked, not trusted to memory.

Usage:
    python scripts/check_rules.py PROJECT_DIR [--require-approved-plan]

Exit code 0 = all checks pass, 1 = at least one violation (printed as file:line).
Checks:
  R1 authorization  - the request model forbids extra fields; ask() derives filters via filters_for();
                      search() is never called with filters taken from the request.
  R2 no silent fakes - no except block that switches to the offline stub, keyword-only search or a
                      canned answer; the API labels the stub (llm_is_test_stub).
  R3 cite or abstain - guard() is applied to model output in the pipeline.
  R4 untrusted text  - passages are wrapped and tag breakout is escaped; no innerHTML assignment in
                      frontend/; system prompt keeps the "untrusted data" rule.
  R6 secrets         - no key-looking strings in project files; .env not tracked by git.
  R7 keep it small   - one HTML page, no external CDN.
  Gate               - PLAN.md has a Status line (and is approved, with --require-approved-plan).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

KEY_PATTERN = re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}")
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".index", "logs", "eval_runs", ".pytest_cache"}
FAKE_FALLBACK = re.compile(r"""=\s*["']offline["']|LLM_PROVIDER|keyword[_ ]only|bm25_only|canned|cached_answer|placeholder|sample answer""", re.I)


def except_bodies(text: str):
    """Yield (line_number, body_text) for every except block, using indentation."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith("except") or not stripped.rstrip().endswith(":"):
            continue
        indent = len(line) - len(stripped)
        body = []
        for nxt in lines[i + 1:]:
            if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                break
            body.append(nxt)
        yield i + 1, "\n".join(body)


def project_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and not (set(p.relative_to(root).parts) & SKIP_DIRS) and p.name != ".env":
            yield p


def line_of(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def read(root: Path, rel: str) -> str:
    p = root / rel
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def check(root: Path, require_approved: bool) -> list[str]:
    v: list[str] = []

    # R1 authorization
    api = read(root, "backend/api.py")
    if not api:
        v.append("backend/api.py: missing")
    elif 'extra="forbid"' not in api and "extra='forbid'" not in api:
        v.append("backend/api.py: request model must set extra=\"forbid\" so clients cannot send filters (R1)")
    for m in re.finditer(r"\b(filters|filter|allowed_folders|groups)\s*:\s*(dict|list)", api):
        v.append(f"backend/api.py:{line_of(api, m.start())}: request accepts '{m.group(1)}' from the client (R1)")
    pipe = read(root, "backend/pipeline.py")
    if "filters_for(" not in pipe:
        v.append("backend/pipeline.py: ask() must derive filters with auth.filters_for() (R1)")
    for m in re.finditer(r"search\([^)]*req\.", pipe + api):
        v.append(f"search() called with request data near: {m.group(0)[:60]} (R1)")

    # R2 no silent fakes
    for p in (root / "backend").glob("*.py") if (root / "backend").is_dir() else []:
        text = p.read_text(encoding="utf-8", errors="replace")
        for lineno, body in except_bodies(text):
            m = FAKE_FALLBACK.search(body)
            if m:
                v.append(f"{p.relative_to(root)}:{lineno}: except block falls back to '{m.group(0)}' (R2)")
    if api and "llm_is_test_stub" not in api:
        v.append("backend/api.py: responses must expose llm_is_test_stub so the stub is labelled (R2)")

    # R3 cite or abstain
    if pipe and "guard(" not in pipe:
        v.append("backend/pipeline.py: model output must pass through generate.guard() (R3)")

    # R4 untrusted text
    gen = read(root, "backend/generate.py")
    if gen:
        if "untrusted" not in gen.lower():
            v.append("backend/generate.py: system prompt lost the 'passages are untrusted data' rule (R4)")
        if "/passage" not in gen or ".replace(" not in gen:
            v.append("backend/generate.py: passage text must be escaped against tag breakout (R4)")
    for p in (root / "frontend").glob("*") if (root / "frontend").is_dir() else []:
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"(innerHTML|outerHTML)\s*\+?=|insertAdjacentHTML|document\.write\(", text):
            v.append(f"{p.relative_to(root)}:{line_of(text, m.start())}: unsafe HTML sink '{m.group(0)}', use textContent (R4)")
        for m in re.finditer(r"(src|href)=\"https?://", text):
            v.append(f"{p.relative_to(root)}:{line_of(text, m.start())}: external CDN/link in frontend (R7)")
    pages = list((root / "frontend").glob("*.html")) if (root / "frontend").is_dir() else []
    if len(pages) > 1:
        v.append(f"frontend/: {len(pages)} HTML pages; the rule is one page unless PLAN.md justifies more (R7)")

    # R6 secrets
    for p in project_files(root):
        if p.suffix in {".zip", ".pdf", ".png", ".jpg", ".npy", ".pkl"}:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in KEY_PATTERN.finditer(text):
            v.append(f"{p.relative_to(root)}:{line_of(text, m.start())}: possible API key (R6)")
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", ".env"], cwd=root,
                             capture_output=True, text=True)
    if tracked.returncode == 0:
        v.append(".env is tracked by git (R6)")

    # Gate
    plan = read(root, "PLAN.md")
    status = re.search(r"^Status:\s*(\w+)", plan, re.M)
    if not status:
        v.append("PLAN.md: missing 'Status:' line (gate)")
    elif require_approved and status.group(1).lower() != "approved":
        v.append(f"PLAN.md: Status is '{status.group(1)}', must be 'approved' before feature code (gate)")
    return v


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path)
    ap.add_argument("--require-approved-plan", action="store_true")
    args = ap.parse_args()
    root = args.project.resolve()
    if not root.is_dir():
        print(f"ERROR: {root} is not a folder", file=sys.stderr)
        return 1
    violations = check(root, args.require_approved_plan)
    if violations:
        print(f"RULE CHECK FAILED: {len(violations)} violation(s)")
        for item in violations:
            print(f"  - {item}")
        return 1
    print("RULE CHECK PASSED: authorization, no silent fakes, cite-or-abstain, untrusted text, secrets, size, plan gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
