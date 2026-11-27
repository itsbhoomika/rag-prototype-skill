#!/usr/bin/env python3
"""Validate a skill folder against the rules in "The Complete Guide to Building Skills for Claude".

Usage:
    python dev/scripts/validate_skill.py [SKILL_DIR]      (default: rag-prototype-builder)

Each check prints PASS/FAIL with the guide section it comes from. Exit code 1 on any FAIL.
Needs PyYAML (pip install pyyaml).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # explicit failure, no silent skip
    sys.exit("PyYAML is required: pip install pyyaml")

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
results: list[tuple[bool, str]] = []


def check(ok: bool, msg: str) -> bool:
    results.append((bool(ok), msg))
    return bool(ok)


def instruction_files(skill: Path) -> list[Path]:
    """Files Claude reads as instructions: SKILL.md and references/. Assets are templates, not instructions."""
    return [skill / "SKILL.md", *sorted((skill / "references").rglob("*.md"))]


def main() -> int:
    root = Path(__file__).resolve().parents[2]  # repo root (this file is dev/scripts/)
    skill = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root / "rag-prototype-builder"

    # Technical requirements: file structure
    check(KEBAB.match(skill.name), f"folder name '{skill.name}' is kebab-case [Critical rules: folder naming]")
    names = [p.name for p in skill.iterdir()]
    check("SKILL.md" in names, "SKILL.md exists with exact spelling [Critical rules: SKILL.md naming]")
    check(not [n for n in names if n.lower() == "skill.md" and n != "SKILL.md"], "no SKILL.md spelling variants")
    readmes = [str(p.relative_to(skill)) for p in skill.rglob("*") if p.name.lower() == "readme.md"]
    check(not readmes, f"no README.md inside the skill folder [Critical rules: No README.md] {readmes or ''}")
    if "SKILL.md" not in names:
        return report()

    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not check(m, "YAML frontmatter has --- delimiters [YAML frontmatter]"):
        return report()
    raw_fm, body = m.group(1), m.group(2)
    try:
        fm = yaml.safe_load(raw_fm)
        check(isinstance(fm, dict), "frontmatter parses with safe YAML [Reference B: no code execution]")
    except yaml.YAMLError as e:
        check(False, f"frontmatter parses with safe YAML: {e}")
        return report()

    # Field requirements
    name = str(fm.get("name", ""))
    check(KEBAB.match(name), f"name '{name}' is kebab-case, no spaces or capitals [Field requirements: name]")
    check(name == skill.name, "name matches folder name [Field requirements: name]")
    check("claude" not in name and "anthropic" not in name, "name has no reserved 'claude'/'anthropic' [Security restrictions]")
    desc = str(fm.get("description", ""))
    check(0 < len(desc) <= 1024, f"description length {len(desc)} is 1..1024 chars [Field requirements: description]")
    check(re.search(r"\bUse when\b", desc), "description says WHEN to use it ('Use when ...') [description: WHAT + WHEN]")
    check(len(desc.split(".")[0].split()) >= 5, "description starts with WHAT it does [description: WHAT + WHEN]")
    check(re.search(r'"[^"]+"', desc), "description includes quoted trigger phrases users would say [description]")
    check(re.search(r"\b(md|pdf|csv|txt|json|html)\b", desc), "description mentions relevant file types [description]")
    check(re.search(r"\bDo NOT use\b", desc), "description has negative triggers to prevent over-triggering [Troubleshooting]")
    check("<" not in raw_fm and ">" not in raw_fm, "no XML angle brackets in frontmatter [Security restrictions]")
    if "compatibility" in fm:
        check(1 <= len(str(fm["compatibility"])) <= 500, "compatibility is 1..500 chars [Field requirements]")
    if "license" in fm:
        check(str(fm["license"]) in {"MIT", "Apache-2.0"} or fm["license"], "license set [Field requirements]")
    meta = fm.get("metadata") or {}
    check(isinstance(meta, dict) and re.match(r"^\d+\.\d+\.\d+$", str(meta.get("version", ""))),
          "metadata.version is semver [Reference A: update version in metadata]")
    check(isinstance(meta, dict) and meta.get("author"), "metadata.author set [Field requirements: metadata]")

    # Writing effective skills
    words = len(body.split())
    check(words < 5000, f"SKILL.md body is {words} words (< 5,000) [Large context issues]")
    for f in instruction_files(skill):
        t = f.read_text(encoding="utf-8")
        check("<" not in t and ">" not in t, f"no XML angle brackets in {f.relative_to(skill)} [Reference A: No XML tags anywhere]")
    check(re.search(r"^## .*CRITICAL", body, re.M | re.I), "critical instructions are at the top under a CRITICAL header [Instructions not followed]")
    check(re.search(r"^## Examples", body, re.M), "Examples section present [Writing the main instructions]")
    check(re.search(r"^## Troubleshooting", body, re.M), "Troubleshooting / error handling section present [Include error handling]")
    check(len(re.findall(r"^### Example \d", body, re.M)) >= 2, "at least 2 concrete examples [Start with use cases: 2-3]")
    check(len(re.findall(r"\*\*Gate", body)) >= 4, "workflow steps have validation gates [Pattern 1 / Category 2]")

    # Progressive disclosure: every referenced bundled file exists, and every reference is linked
    linked = set(re.findall(r"`((?:references|scripts|assets)/[^`\s]+)[`\s]", body))
    missing = sorted(p for p in linked if not (skill / p).exists())
    check(not missing, f"all referenced files exist {missing or ''} [Reference bundled resources clearly]")
    unlinked = sorted(str(p.relative_to(skill)) for p in (skill / "references").glob("*.md")
                      if str(p.relative_to(skill)) not in linked)
    check(not unlinked, f"every reference file is linked from SKILL.md {unlinked or ''} [Progressive disclosure]")
    scripts = sorted(str(p.relative_to(skill)) for p in (skill / "scripts").glob("*.py"))
    check(all(any(s in x for x in linked) for s in scripts), "every script is documented in SKILL.md")
    return report()


def report() -> int:
    for ok, msg in results:
        print(("PASS  " if ok else "FAIL  ") + msg)
    failed = sum(not ok for ok, _ in results)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
