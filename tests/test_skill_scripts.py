"""Deterministic tests for the skill's own scripts (no keys, no network).

Run: python -m pytest -q   (needs pytest and pyyaml)
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "rag-prototype-builder"


def load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


scaffold = load(SKILL / "scripts" / "scaffold.py")
rules = load(SKILL / "scripts" / "check_rules.py")


# ---------------------------------------------------------------- validate_skill.py
def test_skill_passes_guide_validation():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_skill.py"), str(SKILL)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
    assert "FAIL" not in r.stdout


def test_validator_rejects_bad_skill(tmp_path):
    bad = tmp_path / "Bad_Skill"
    bad.mkdir()
    (bad / "SKILL.md").write_text("---\nname: Bad Skill\ndescription: Helps with <projects>.\n---\nbody\n")
    (bad / "README.md").write_text("no")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_skill.py"), str(bad)],
                       capture_output=True, text=True)
    assert r.returncode == 1
    for expected in ["folder name", "README.md", "kebab-case", "Use when", "angle brackets"]:
        assert any(expected in line for line in r.stdout.splitlines() if line.startswith("FAIL")), expected


# ---------------------------------------------------------------- scaffold.py
def test_scaffold_creates_project_with_real_names(tmp_path):
    files = scaffold.scaffold(tmp_path / "app")
    for f in [".env.example", ".gitignore", "README.md", ".claude/agents/project-manager.md",
              "CLAUDE.md", "PLAN.md", "ci.sh", "backend/pipeline.py", "frontend/index.html", "data/users.json"]:
        assert f in files, f
    assert not any(f.startswith(("env.example", "gitignore", "dot-claude", "README.template")) for f in files)


def test_scaffold_never_overwrites(tmp_path):
    target = tmp_path / "app"
    target.mkdir()
    (target / "mine.txt").write_text("keep me")
    with pytest.raises(FileExistsError):
        scaffold.scaffold(target)
    assert (target / "mine.txt").read_text() == "keep me"
    assert not (target / "backend").exists()


def test_scaffold_no_sample(tmp_path):
    scaffold.scaffold(tmp_path / "app", sample=False)
    assert list((tmp_path / "app" / "data" / "sample").iterdir()) == []
    assert (tmp_path / "app" / "data" / "users.json").read_text().strip() == '{"users": {}}'


def test_template_has_no_env_file():
    assert not (SKILL / "assets" / "template" / ".env").exists()


# ---------------------------------------------------------------- check_rules.py
@pytest.fixture
def project(tmp_path):
    scaffold.scaffold(tmp_path / "app")
    return tmp_path / "app"


def test_rules_pass_on_template(project):
    assert rules.check(project, require_approved=False) == []


def test_rules_require_approved_plan(project):
    v = rules.check(project, require_approved=True)
    assert any("must be 'approved'" in x for x in v)
    plan = project / "PLAN.md"
    plan.write_text(plan.read_text().replace("Status: draft", "Status: approved"))
    assert rules.check(project, require_approved=True) == []


def test_rules_catch_innerhtml(project):
    js = project / "frontend" / "app.js"
    js.write_text(js.read_text() + "\nel.innerHTML = passage.text;\n")
    assert any("unsafe HTML sink" in x for x in rules.check(project, False))


def test_rules_catch_client_filters(project):
    api = project / "backend" / "api.py"
    api.write_text(api.read_text().replace('extra="forbid"', 'extra="allow"'))
    assert any("extra=\"forbid\"" in x for x in rules.check(project, False))


def test_rules_catch_silent_fallback(project):
    p = project / "backend" / "pipeline.py"
    p.write_text(p.read_text() + "\n\ndef bad():\n    try:\n        pass\n    except Exception:\n        provider = 'offline'\n")
    assert any("falls back" in x for x in rules.check(project, False))


def test_rules_catch_removed_guard(project):
    p = project / "backend" / "pipeline.py"
    p.write_text(p.read_text().replace("ans = guard(raw, hits)", "ans = raw"))
    assert any("guard()" in x for x in rules.check(project, False))


def test_rules_catch_planted_key(project):
    fake = "sk-ant-" + "x" * 30  # built at runtime so this test file itself holds no key-shaped string
    (project / "backend" / "leak.py").write_text(f'KEY = "{fake}"\n')
    assert any("possible API key" in x for x in rules.check(project, False))


def test_rules_catch_lost_untrusted_rule(project):
    g = project / "backend" / "generate.py"
    g.write_text(g.read_text().replace("untrusted", "trusted"))
    assert any("untrusted" in x for x in rules.check(project, False))
