# Testing and CI

## Fixtures vs the owner's data
- `tests/fixtures/` holds 4 fictional documents, 3 users and 11 questions. Unit, API and fixture-regression tests use only these, so they stay deterministic and pass whatever the owner puts in `data/`.
- `data/` is the owner's. It is measured by `backend.cli eval` and by the owner-data regression gate.
- Never edit fixtures to make a test pass. Add an owner question instead.

## `./ci.sh` stages (stops at the first failure)
| Stage | Checks | Cost |
|---|---|---|
| 1. Setup | `.venv` exists, packages import | free |
| 2. Static checks | syntax, then `scripts/check_rules.py` (copied in by `scaffold.py`): client filters, silent fallbacks, the guard, untrusted-text rule, HTML sinks, CDN, key-looking strings, `.env` tracked | free |
| 3. Unit tests | ingestion, chunking, authorization, guard, injection escaping, failures raise | free |
| 4. API tests | response shape, 403, 422 for extra fields, 502 on provider failure, frontend escaped | free |
| 5. Regression | fixture golden set scores at least `regression_baseline.json`; once `data/questions.jsonl` has items, the owner's set must score at least `data_baseline.json` (the first run saves it and shows as skipped) | free |
| 6. Live (`--live`) | `doctor --require-real` (refuses the stub) + ingest + `eval --strict` (fails on any failed item) | API calls |

Also run `python scripts/check_rules.py PROJECT_DIR` (from the skill) after each milestone. It checks the rules that tests may not cover.

## Unit vs regression, in plain words
- **Unit test:** one small behaviour. "Bob can't retrieve policies." "An invented citation P7 is dropped." When it fails, you know exactly what broke.
- **Regression test:** the whole question set must score at least as well as before. It catches changes that quietly make things worse.

## Rules
- Every change ships with a test. A bug fix starts with a failing test that reproduces the bug.
- Tests are deterministic: offline stub, keyword search, fixed fixtures, no network.
- Provider failures are tested with a fake provider that raises. The test asserts the error surfaces (502), not a fallback answer.
- Red stage = no commit.

## Commit flow (explain each command to a learner)
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
- `./ci.sh` checks everything.
- `git status` shows what changed.
- `git add -A` stages every change for the snapshot.
- `git commit` saves the snapshot with a message.

Don't commit unless the owner asks, and never commit `.env`.
