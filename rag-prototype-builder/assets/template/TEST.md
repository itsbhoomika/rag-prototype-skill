# Testing and CI

Run this before every commit of a major change:

```bash
./ci.sh
```

It works like a CI/CD pipeline: stages run in order, and the first failure stops everything. A red stage means don't commit; fix it first.

## The pipeline

| Stage | What it checks | Command it runs | Cost |
|---|---|---|---|
| 1. Setup | `.venv` exists and packages import | `python -c "import ..."` | free |
| 2. Static checks | Python syntax; no API keys in files; `.env` not tracked by git; no `innerHTML =` and no external CDN in the frontend | `compileall`, `grep`, `git ls-files` | free |
| 3. Unit tests | Each part on its own: ingestion, chunking, authorization, citation guard, injection escaping, failures raise instead of faking | `pytest tests/test_pipeline.py` | free |
| 4. API tests | The HTTP contract: response shape, 403 for unknown users, 422 if a client sends its own filters, 502 when a provider fails, frontend served and escaped | `pytest tests/test_api.py` | free |
| 5. Regression tests | The golden questions still score at least as well as the saved baseline | `pytest tests/test_regression.py` | free |
| 6. Live eval (optional) | The real model and embeddings from `.env` work end to end, and real answer quality | `./ci.sh --live` | API calls |

Stages 1–5 use the `offline` test stub and keyword search, so they are **deterministic**: the same code always gives the same result, with no keys and no network.

## Unit vs regression tests, in plain words

- **Unit test:** checks one small behaviour. "Alice can't retrieve catalog files." "An invented citation `[P7]` gets dropped." If it fails, you know exactly what broke.
- **Regression test:** checks you didn't make things *worse* overall. It runs all the questions in `data/questions.jsonl` and compares the scores with `tests/regression_baseline.json`. Any metric below its baseline fails.

What the regression numbers mean offline:
- `hit@k` and `mrr` measure **search**. Those are real signals.
- `citation_hit` and the abstention scores go through the stub, so they catch plumbing changes (guard, gate, prompt wiring), **not** answer quality. Use `./ci.sh --live` for quality.

## When to do what

| Situation | Run |
|---|---|
| Small edit while working | `.venv/bin/python -m pytest -q` (all tests, ~2 s) |
| Before any commit of a major change | `./ci.sh` |
| Before a demo, or after changing provider, prompt or model | `./ci.sh --live` |
| You improved search on purpose and scores went **up** | Update the baseline (below), then commit it with the change |
| You added or changed questions | Update the baseline, and say why in the commit message |

Update the baseline (only on purpose, never to make a red build green):
```bash
UPDATE_BASELINE=1 .venv/bin/python -m pytest tests/test_regression.py
```

## Adding a test with every change

Rule from `CLAUDE.md`: a change isn't done without a test.

- New behaviour: add a unit test in `tests/test_pipeline.py` (or `tests/test_api.py` for endpoints).
- Fixed a bug: first add a test that fails because of the bug, then fix it. The test stops the bug coming back.
- New kind of question that matters: add it to `data/questions.jsonl`, then update the baseline.

## Commit flow (git, step by step)

```bash
./ci.sh
```
```bash
git status
```
```bash
git add -A
```
```bash
git commit -m "Describe the change"
```

1. `./ci.sh` checks everything.
2. `git status` shows what changed.
3. `git add -A` selects all changes for the snapshot.
4. `git commit` saves the snapshot.

Optional: make git run CI automatically before every commit. A "pre-commit hook" is a script git runs before saving a commit; if it fails, the commit is blocked.
```bash
printf '#!/bin/sh\n./ci.sh\n' > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

## Not covered yet
- No hosted CI (e.g. GitHub Actions). With one, a workflow would run the same `./ci.sh` on every push.
- No linter or type checker (e.g. ruff, mypy). Add one only if the plan calls for it.
- The live eval has no pass/fail threshold yet. It prints metrics and saves them in `eval_runs/` for you to compare.
