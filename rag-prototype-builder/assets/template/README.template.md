# RAG Prototype

Ask questions about a folder of documents. Answers cite their sources or say "I don't know". Each user only sees the folders they're allowed to see.

```
CLAUDE.md                       rules for Claude (includes the standing build prompt)
PLAN.md                         the project plan, filled in by the project-manager agent
.claude/agents/project-manager.md
backend/                        Python: ingest, search, generate, auth, pipeline, eval, API, CLI
frontend/                       index.html + app.js (served by the backend)
data/sample/                    your documents (one top-level folder per access group)
data/users.json                 users and the folders they may see (identity is simulated: no login)
data/questions.jsonl            your golden eval questions
tests/                          tests that run without API keys
tests/fixtures/                 fixed fictional data the tests use, so they pass whatever is in data/
```

## Run it
```bash
uv venv && uv pip install -r requirements.txt
cp .env.example .env        # put your API key in .env (LLM_PROVIDER=offline runs with no key, as a labelled test stub)
.venv/bin/python -m backend.cli doctor
.venv/bin/python -m backend.cli ingest
.venv/bin/uvicorn backend.api:app --reload
```
Open http://127.0.0.1:8000, pick a user, ask a question.

## Test it
```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m backend.cli eval --label baseline
```
