# RAG Prototype

Ask questions about a folder of documents. Answers cite their sources or say "I don't know". Each user only sees the folders they're allowed to see.

```
CLAUDE.md                       rules for Claude (includes the standing build prompt)
PLAN.md                         the project plan, filled in by the project-manager agent
.claude/agents/project-manager.md
backend/                        Python: ingest, search, generate, auth, pipeline, eval, API, CLI
frontend/                       index.html + app.js (served by the backend)
data/sample/                    fictional sample documents
data/users.json                 fictional users and the folders they may see
data/questions.jsonl            eval questions
tests/                          tests that run without API keys
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
