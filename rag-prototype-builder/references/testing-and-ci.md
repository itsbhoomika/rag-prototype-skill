# Testing and CI

## `./ci.sh` stages (stops at the first failure)
| Stage | Checks | Cost |
|---|---|---|
| 1. Setup | `.venv` exists, packages import | free |
| 2. Static checks | syntax, no key-looking strings, `.env` not tracked, no `innerHTML =`, no CDN | free |
| 3. Unit tests | ingestion, chunking, authorization, guard, injection escaping, failures raise | free |
| 4. API tests | response shape, 403, 422 for extra fields, 502 on provider failure, frontend escaped | free |
| 5. Regression | golden set scores at least the baseline | free |
| 6. Live (`--live`) | `doctor` + ingest + eval with real providers | API calls |

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
