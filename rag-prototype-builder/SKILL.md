---
name: rag-prototype-builder
description: Builds a working, tested RAG (retrieval-augmented generation) prototype end to end - document ingestion and chunking, BM25 plus optional embedding hybrid search, cited answers with a cite-or-abstain guard, server-side per-user authorization, prompt-injection defences, evals and a local CI pipeline, with a FastAPI backend and a one-page frontend. Use when the user asks to "build a RAG", "make a chatbot over my documents", "question answering over PDFs, CSVs or markdown", "retrieval with citations", "document search with access control", or to improve an existing RAG or document Q&A prototype - "add embeddings", "hybrid search", "reranking", "retrieval evals" such as hit@k, MRR or precision@k, or fixing missed and paraphrased questions. Handles md, txt, pdf, csv, json and html files. Do NOT use for general LLM chat apps without documents, fine-tuning, or tuning a production vector database at scale.
license: MIT
compatibility: Designed for Claude Code (needs a file system, bash and Python 3.10+, with uv or pip). Network access is needed only for real model providers; the labelled offline test stub and all tests run without keys.
metadata:
  author: itsbhoomika
  version: 1.1.0
  category: workflow-automation
  tags: [rag, retrieval, citations, evals, fastapi, prompt-injection, authorization]
  documentation: https://github.com/itsbhoomika/rag-prototype-skill
---

# RAG Prototype Builder

Turns a brief ("answer questions about these documents, each user sees only their folders") into a working, tested RAG app, starting from a tested template and measuring each change.

## CRITICAL rules

1. **Plan before feature code** on a new build (Path B). The owner approves; you record it.
2. **Authorization is server-side**, applied inside retrieval before any top-k cut. The client sends only `user_id`; never accept a filter from it. Identity is **simulated** (no login): say so in the plan, UI and report.
3. **No silent fakes.** A failing provider, embedder or index raises and shows the error. Never fall back to keyword-only, cached answers, sample data or the `offline` stub unless the owner chooses it. The stub is always labelled.
4. **Cite or abstain.** The guard checks shape, citations and that numbers come from the cited passages. Never weaken it to raise a metric.
5. **Retrieved text is untrusted data.** Keep the passage wrapping and the system-prompt rule. UI uses `textContent`, never `innerHTML`.
6. **Feature order:** BM25, then hybrid embeddings, then reranking, each only after `eval` shows the need.
7. **Secrets live in `.env` only.** Never print, log or commit keys, and never ask for one in chat.
8. **Keep it small.** One backend, one page; nothing extra unless `PLAN.md` justifies it.

Rules 2–5 and 7–8 are checked by code: `python scripts/check_rules.py PROJECT_DIR`. Run it instead of relying on memory.

## Pick a path

| The owner wants | Path |
|---|---|
| To try it, practise, or see a demo | **A. Sample run**, no plan needed |
| A RAG over their own documents | **B. New build**, plan first |
| To improve an existing prototype | **C. Improve**, measure first |

## Path A: Sample run
```bash
python scripts/scaffold.py PROJECT_DIR
cd PROJECT_DIR && uv venv && uv pip install -r requirements.txt && cp .env.example .env
./ci.sh
```
Set `LLM_PROVIDER=offline` in `.env` to run without a key, then run `.venv/bin/python -m backend.cli ingest` and `ask --user alice "What is the return window for kayaks?"`.

**Gate:** `CI PASSED`, alice gets a cited answer, and bob (catalog only) gets an abstention for the same question.

## Path B: New build

### Step 1: Understand the brief
Ask only what changes the build:
- where the documents are, and their file types
- the users, and which folders each may see
- whether the data contains personal or sensitive information
- **3–5 real questions with the answer you expect.** These seed the golden set.
- the model provider, only if they want real answers now (the stub covers building)

**Gate:** you can state the goal in one sentence and list every user and their folders.

### Step 2: Scaffold
Run `python scripts/scaffold.py PROJECT_DIR --no-sample`, then copy the owner's documents into `data/sample/` (one top-level folder per access group) and write `data/users.json`. Install and run `./ci.sh` as in Path A. The tests use `tests/fixtures/`, so they pass whatever the owner's data is.

**Gate:** `CI PASSED`. If it fails, see `references/troubleshooting.md` before changing code.

### Step 3: Plan
Fill `PLAN.md`: the goal, the users and folders, the milestones below, `ASSUMPTION:` lines, privacy risks and what is out of scope. Keep it to one screen. Map the brief using `references/adapting-to-a-new-brief.md`. Set `Status: draft` and stop.

When the owner says it's approved, change the line to `Status: approved (owner, in chat, DATE)`.

**Gate:** `python scripts/check_rules.py PROJECT_DIR --require-approved-plan` passes.

### Step 4: Milestones
| # | Milestone | Proven by |
|---|---|---|
| M1 | Vertical slice: owner's docs ingested, BM25, cited answers, the access rules, and the 3–5 golden questions plus one unanswerable and one forbidden-folder question per user | per-user access test (allowed passage found, forbidden never returned), `eval --label baseline`, data baseline saved |
| M2 | Golden set grown to 10–30 questions across file types and users | eval, with failures grouped by type |
| M3 | Hybrid embeddings, only if M2 shows retrieval misses | beats M2 on `hit@k` or `mrr` |
| M4 | Reranking, only if the right passage is retrieved but ranked low | beats M3 on `mrr` |

For each one: write the test first, make the smallest change, run `pytest` and `check_rules.py`, and run `eval` if retrieval, prompts or chunking changed. Compare runs on the same questions and the same `TOP_K`, and include `latency_p50_ms` in the keep-or-drop decision. Record the real output in the `PLAN.md` row.

**Gate per milestone:** tests green, rule check passed, evidence in `PLAN.md`.

### Step 5: Verify and report
`./ci.sh`, and before a demo `./ci.sh --live`. The live stage refuses the stub and fails if any golden item fails. It costs API calls, so tell the owner first.

Report, as separate measurements with item counts:
- retrieval (`hit@k`, `mrr`)
- citation support (`citation_hit`, grounding abstentions)
- answer correctness (`judge_accuracy`, live only)
- abstention (`abstain_recall`, `abstain_precision`)

Then list the trade-offs, the failure types and what isn't built, including simulated identity.

**Gate:** `CI PASSED` (live, if a key exists), and every milestone row has evidence.

## Path C: Improve an existing prototype
1. Make sure a baseline eval exists. If not, run M1's eval first (rule 6).
2. Make one change, for example `EMBED_PROVIDER` set by the owner in `.env`, then re-ingest.
3. Run `eval --label NAME` and compare with the baseline on the same questions.
4. Keep the change only if a metric improved without a latency cost the owner rejects. Then update the baseline on purpose.

**Gate:** the comparison table is in `PLAN.md`.

## Examples

### Example 1: Own documents, two roles
"Build a RAG over the PDFs in ./handbook. HR sees everything, staff only see policies."
Path B, with `hr: ["*"]` and `staff: ["policies"]`. M1 includes a test that staff never retrieve a passage outside `policies`.

### Example 2: Practice
"Spin up a RAG prototype I can practise on." Path A.

### Example 3: Paraphrases missed
"Retrieval misses paraphrased questions, add embeddings." Path C, with the change being `EMBED_PROVIDER`, compared using `--label hybrid`.

## Troubleshooting
| Error | Fix |
|---|---|
| `No index in .index` | Run `.venv/bin/python -m backend.cli ingest` |
| HTTP 403 `unknown user` | Add the user to `data/users.json` on the server |
| HTTP 502 `AuthenticationError` | The owner fixes `.env`. Run `backend.cli doctor`, which never prints values |
| Every answer abstains | Read the reason in `logs/traces.jsonl`. Fix retrieval or the prompt, **not** the guard |
| `RULE CHECK FAILED` | Fix the code at the `file:line` shown, not the checker |

The full table is in `references/troubleshooting.md`.

## References (load only what the step needs)
- `references/architecture.md`: components, data flow, API contract, trade-offs (Step 3)
- `references/adapting-to-a-new-brief.md`: mapping a brief, data and users onto the template (Steps 1–3)
- `references/ingestion-and-chunking.md`: loaders, chunk size and overlap (M1)
- `references/retrieval.md`: BM25, hybrid RRF, what the access mask guarantees, reranking (M1, M3, M4)
- `references/generation-and-guardrails.md`: prompt, passage wrapping, the guard and its limits (M1)
- `references/authorization.md`: the server-side model, simulated identity, required tests (M1)
- `references/evaluation.md`: golden-set format, metrics, baselines (M1, M2)
- `references/providers.md`: models, the offline stub, `doctor` (Step 2, model changes)
- `references/testing-and-ci.md`: CI stages, fixtures vs owner data (Steps 2, 5)
- `references/nextjs-supabase-variant.md`: TypeScript + pgvector port with `assets/supabase-schema.sql`, only if asked
- `references/troubleshooting.md`: all errors
- `references/resources.md`: official skills and RAG docs

## Scripts
- `scripts/scaffold.py PROJECT_DIR [--no-sample]`: copies `assets/template/` into an empty folder
- `scripts/check_rules.py PROJECT_DIR [--require-approved-plan]`: rule checks; exit 1 lists `file:line`
