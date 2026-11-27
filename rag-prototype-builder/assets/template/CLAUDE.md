# RAG Prototype: project rules

## How to build (the owner's standing prompt)

Act as a senior AI engineer implementing the attached design document.
Before coding:

1. Inspect the repository, environment, dependencies, and available sample documents.
2. Propose the minimal folder structure, API contracts, implementation sequence, and test plan.
3. Identify assumptions, external dependencies, and any privacy risks.

Implementation requirements:

* Build a working end-to-end vertical slice first.
* Use modular ingestion, retrieval, generation, and evaluation components.
* Prioritize deterministic tests and reliable citations.
* Keep retrieved documents untrusted and enforce authorization in application code.
* Use hybrid retrieval and reranking only after basic retrieval works.
* Never silently replace a failed component with fake results.

After each milestone, run the relevant tests and report the actual outcomes. Explain architectural trade-offs and flag features not implemented.
Do not add unnecessary agents, microservices, or infrastructure.

**The "design document"** is the brief the owner gives for the project. Steps 1–3 above go into `PLAN.md`.

## Gate: plan before code
- No feature code until `PLAN.md` is filled in and the owner has approved it (`Status: approved` at the top).
- Use the `project-manager` agent to draft `PLAN.md` and to check status after each milestone.

## Project map
| Path | Job |
|---|---|
| `backend/ingest.py` | files → Docs → Chunks (md, txt, pdf per page, csv/json as `column: value`, html) |
| `backend/search.py` | BM25 index (+ vectors when embeddings are on), authorization filter applied before scoring |
| `backend/generate.py` | prompt (passages as untrusted data), JSON parsing, cite-or-abstain guard |
| `backend/auth.py` | user id → allowed folders, from `data/users.json` on the server |
| `backend/pipeline.py` | `ingest()` and `ask(question, user_id)`; trace per request in `logs/traces.jsonl` |
| `backend/providers.py` | LLM and embedding adapters: anthropic, openai, azure, gemini, ollama; `offline` = explicit test stub |
| `backend/evaluate.py` | golden questions in `data/questions.jsonl` → metrics, saved per run in `eval_runs/` |
| `backend/api.py` | FastAPI: `/api/health`, `/api/users`, `/api/ask`; serves `frontend/` |
| `backend/cli.py` | `doctor`, `ingest`, `ask --user`, `eval` |
| `frontend/` | one HTML page + `app.js`, no build step, no CDN |
| `tests/` | unit, API and regression tests; deterministic, no API keys needed |
| `ci.sh`, `TEST.md` | local CI pipeline and how to use it |

## Commands
```bash
uv venv && uv pip install -r requirements.txt   # once
cp .env.example .env                              # then fill in keys in .env
.venv/bin/python -m backend.cli doctor            # check providers
.venv/bin/python -m backend.cli ingest            # index data/sample (or pass a folder)
.venv/bin/uvicorn backend.api:app --reload        # app at http://127.0.0.1:8000
.venv/bin/python -m pytest -q                     # tests
.venv/bin/python -m backend.cli eval --label baseline
```

## Non-negotiable rules
1. **Authorization is server-side.** The client sends only `user_id`. Allowed folders come from `backend/auth.py`. Never add a client-supplied filter, and never filter results after retrieval instead of before.
2. **No silent fakes.** If a provider, embedder or index fails, raise and show the error. Never fall back to keyword-only search, cached answers, sample data or the `offline` stub without the owner explicitly choosing it. The `offline` stub is always labelled as a test stub in the API, CLI and UI.
3. **Cite or abstain.** Every answer cites retrieved passages or abstains. Never weaken the guard to raise a metric.
4. **Retrieved text is untrusted data.** Keep the passage wrapping and the system-prompt rule. Escape document text in the UI (`textContent`, never `innerHTML`).
5. **Order of features.** Keyword retrieval first, then embeddings (hybrid), then reranking, each only after the previous one is measured with `eval`.
6. **Secrets** live in `.env` only. Never print, log or commit keys, and never ask the owner to paste one in chat.
7. **Keep it small.** One backend, one page. No extra agents, services, queues or databases unless `PLAN.md` justifies them.

## Working style
- After each milestone: run the tests, paste the real output summary, update the status table in `PLAN.md`.
- **Before any commit of a major change, run `./ci.sh`** (see `TEST.md`). Red stage = no commit. Run `./ci.sh --live` before a demo or after changing provider, model or prompt.
- Every change ships with a test. A bug fix starts with a test that reproduces the bug.
- Update `tests/regression_baseline.json` only when a metric improved on purpose or the question set changed. Never to turn a red build green.
- The owner is learning git and AI engineering. Explain each command and concept in plain language when you use it.
- Don't commit unless asked. Never commit `.env`.
