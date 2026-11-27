#!/usr/bin/env python3
"""Copy the tested RAG prototype template into a new project folder.

Usage:
    python scripts/scaffold.py TARGET_DIR [--no-sample]

- Refuses to write into a folder that already has files (nothing is overwritten).
- Renames packaging-safe names back to their real names:
    README.template.md -> README.md, env.example -> .env.example,
    gitignore -> .gitignore, dot-claude/ -> .claude/
- --no-sample leaves data/sample, data/questions.jsonl and data/users.json as empty
  placeholders, for when the owner brings their own documents.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "template"
RENAMES = {
    "README.template.md": "README.md",
    "env.example": ".env.example",
    "gitignore": ".gitignore",
    "dot-claude": ".claude",
}
SKIP = {"__pycache__", ".pytest_cache", ".venv", ".index", "logs", "eval_runs", ".DS_Store"}


def scaffold(target: Path, sample: bool = True) -> list[str]:
    if not TEMPLATE.is_dir():
        raise FileNotFoundError(f"Template not found at {TEMPLATE}. Is the skill folder complete?")
    if target.exists() and any(p.name != ".git" for p in target.iterdir()):
        raise FileExistsError(f"{target} is not empty. Choose an empty folder; nothing was copied.")
    target.mkdir(parents=True, exist_ok=True)

    shutil.copytree(TEMPLATE, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*SKIP))
    for src, dst in RENAMES.items():
        if (target / src).exists():
            (target / src).rename(target / dst)
    (target / "ci.sh").chmod(0o755)

    if not sample:
        shutil.rmtree(target / "data" / "sample")
        (target / "data" / "sample").mkdir()
        (target / "data" / "questions.jsonl").write_text("")
        (target / "data" / "users.json").write_text('{"users": {}}\n')

    return sorted(str(p.relative_to(target)) for p in target.rglob("*") if p.is_file())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", type=Path)
    ap.add_argument("--no-sample", action="store_true", help="start without the fictional sample data")
    args = ap.parse_args()
    try:
        files = scaffold(args.target.resolve(), sample=not args.no_sample)
    except (FileExistsError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"Created {len(files)} files in {args.target}")
    print("Next steps:")
    print(f"  cd {args.target}")
    print("  uv venv && uv pip install -r requirements.txt")
    print("  cp .env.example .env    # owner fills in keys; LLM_PROVIDER=offline runs without one (labelled test stub)")
    print("  ./ci.sh                 # must be green before any feature work")
    return 0


if __name__ == "__main__":
    sys.exit(main())
