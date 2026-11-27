---
name: rag-prototype-builder
description: Builds a working, tested RAG (retrieval-augmented generation) prototype end to end - document ingestion and chunking, BM25 plus optional embedding hybrid search, cited answers with a cite-or-abstain guard, server-side per-user authorization, prompt-injection defences, evals and a local CI pipeline, with a FastAPI backend and a one-page frontend. Use when the user asks to "build a RAG", "make a chatbot over my documents", "question answering over PDFs, CSVs or markdown", "retrieval with citations", "document search with access control", or to improve an existing RAG or document Q&A prototype - "add embeddings", "hybrid search", "reranking", "retrieval evals" such as hit@k, MRR or precision@k, or fixing missed and paraphrased questions. Handles md, txt, pdf, csv, json and html files. Do NOT use for general LLM chat apps without documents, fine-tuning, or tuning a production vector database at scale.
license: MIT
compatibility: Designed for Claude Code (needs a file system, bash and Python 3.10+, with uv or pip). Network access is needed only for real model providers; the labelled offline test stub and all tests run without keys.
metadata:
  author: itsbhoomika
  version: 1.0.0
  category: workflow-automation
  tags: [rag, retrieval, citations, evals, fastapi, prompt-injection, authorization]
  documentation: https://github.com/itsbhoomika/rag-prototype-skill
---

# RAG Prototype Builder

Turns a brief ("answer questions about these documents, each user sees only their folders") into a working, tested RAG app in one sitting. It starts from a tested template, plans before coding, then builds and measures one milestone at a time.

## CRITICAL rules (check these before every step)

1. **Plan before code.** No feature code until `PLAN.md` says `Status: approved`. The owner approves, not you.
2. **Authorization is server-side and applied before scoring.** The client sends only `user_id`. Allowed folders come from `backend/auth.py`. Never accept a filter from the client. Never filter results after retrieval.
3. **No silent fakes.** If a provider, embedder or index fails, raise and show the error. Never fall back to keyword-only search, cached answers, sample data or the `offline` stub unless the owner chooses it. The stub is always labelled as a test stub.
4. **Cite or abstain.** Every answer cites retrieved passages, or abstains. Never weaken the guard to raise a metric.
5. **Retrieved text is untrusted data.** Keep the passage wrapping, the tag-breakout escaping and the system-prompt rule. In the UI use `textContent`, never `innerHTML`.
6. **Feature order:** keyword retrieval, then embeddings (hybrid), then reranking. Add each one only after `eval` measured the previous one.
7. **Secrets live in `.env` only.** Never print, log or commit keys. Never ask the owner to paste a key into chat.
8. **Keep it small.** One backend, one page. No extra agents, services, queues or databases unless `PLAN.md` justifies them.

Rules 2–5 and 7–8 are checked by code: `python scripts/check_rules.py PROJECT_DIR`. Run it rather than relying on memory.

## Workflow

Follow the steps in order. Each step ends with a **gate**: do not start the next step until the gate passes. If a gate fails, fix the problem and re-run the gate. Do not skip ahead.

### Step 1: Understand the brief
Ask only what changes the build. Typical questions:
- Where are the documents, and what file types are they?
- Who are the users, and which folders may each one see?
- Which model provider and key does the owner have?
- Does the data contain personal or sensitive information?

If the owner has no data yet, use the fictional sample data in the template.

**Gate:** you can state the goal in one sentence and list the users and their folders.

### Step 2: Scaffold from the tested template
```bash
python scripts/scaffold.py PROJECT_DIR
```
Use `--no-sample` if the owner brings their own documents.

Expected output: `Created 34 files in PROJECT_DIR` and the next steps. The script refuses a folder that isn't empty, so nothing gets overwritten.

Then, inside `PROJECT_DIR`:
```bash
uv venv && uv pip install -r requirements.txt
cp .env.example .env
./ci.sh
```
`ci.sh` runs offline with the labelled test stub, so it needs no key. Tell the owner to put their keys in `.env` themselves.

**Gate:** `./ci.sh` prints `CI PASSED`. If it fails, see Troubleshooting before changing any code.

### Step 3: Plan (validation gate)
Fill `PLAN.md` using the standing prompt in the project's `CLAUDE.md`. If the `project-manager` agent is present in `.claude/agents/`, it drafts the plan.

The plan covers:
- goal and minimal folder changes
- API contracts
- 4–6 milestones, each with a test that proves it
- deterministic test plan
- `ASSUMPTION:` lines for the owner to confirm
- external dependencies
- privacy risks
- what is out of scope

Use `references/adapting-to-a-new-brief.md` to map the brief onto the template. Then set `Status: draft` and stop.

**Gate:** the owner changes the line to `Status: approved`. Confirm with:
```bash
python scripts/check_rules.py PROJECT_DIR --require-approved-plan
```

### Step 4: Build milestones (iterative loop)
Default sequence. Adapt it in `PLAN.md`, but keep the order of retrieval features:

| # | Milestone | Proven by |
|---|---|---|
| M1 | Owner's documents ingested; keyword (BM25) retrieval with citations | `pytest`, `backend.cli ask --user ...` |
| M2 | Authorization rules for this brief, applied before scoring | an authorization test per user: allowed passage found, forbidden one never returned |
| M3 | Golden questions + eval baseline (include unanswerable and forbidden-folder questions) | `backend.cli eval --label baseline`, regression baseline saved |
| M4 | Embeddings on (hybrid with RRF), only if M3 shows retrieval misses | eval run that beats M3 on `hit@k` or `mrr` |
| M5 | Reranking, only if M4 shows ranking problems | eval run that beats M4 |

For each milestone, loop:
1. Write or adjust the test first. For a bug fix, write a test that fails because of the bug.
2. Make the smallest change that passes it. See the references for each component.
3. Run `.venv/bin/python -m pytest -q` and `python scripts/check_rules.py PROJECT_DIR`.
4. Run `eval` when retrieval, prompts or chunking changed.
5. Paste the real output summary and update the milestone row in `PLAN.md`.
6. Stop iterating when the milestone's test passes and no metric dropped below the baseline. Don't chase further gains without a plan line for it.

**Gate per milestone:** tests green, rule check passed, evidence recorded in `PLAN.md`.

### Step 5: Verify and report
```bash
./ci.sh
```
Before a demo, or after changing provider, model or prompt, run `./ci.sh --live`. It uses real keys and costs money, so tell the owner first.

Report in plain language:
- what works, with evidence
- metrics, with item counts
- architectural trade-offs
- known failure types
- features not implemented

**Gate:** `CI PASSED`, and every milestone row has evidence.

## Examples

### Example 1: New prototype from the owner's documents
User says: "Build me a RAG over the PDFs in ./handbook. HR sees everything, staff see only the policies folder."

Actions:
1. Step 1: confirm the users and folders.
2. Scaffold with `--no-sample` and copy `./handbook` into `data/sample/`, keeping its folder layout. Write `data/users.json` with `hr: ["*"]` and `staff: ["policies"]`.
3. Draft `PLAN.md` and wait for approval.
4. Build M1–M3. Add an authorization test showing that staff never retrieve a passage from outside `policies`.

Result: a working app at `http://127.0.0.1:8000`. Every answer is cited or abstains, and an eval baseline is saved.

### Example 2: Practice run with fictional data
User says: "Spin up a RAG prototype I can practise on."

Actions:
1. Scaffold with the sample data.
2. Run `./ci.sh`.
3. Run `.venv/bin/python -m backend.cli ingest`, then `ask --user alice "What is the return window for kayaks?"`.

Result: a cited answer from `returns.md`. User `bob`, who may only see `catalog`, gets an abstention for the same question.

### Example 3: Add hybrid search to an existing prototype
User says: "Retrieval misses paraphrased questions, add embeddings."

Actions:
1. Check that a baseline eval exists. If not, create it first (rule 6).
2. Set `EMBED_PROVIDER` in `.env` (the owner does this) and re-ingest.
3. Run eval with `--label hybrid` and compare with the baseline.
4. Keep the change only if `hit@k` or `mrr` improved. Then update the regression baseline, with the reason in the commit message.

Result: hybrid search on, with the measured gain recorded in `PLAN.md`.

## Troubleshooting

| Error | Cause | Solution |
|---|---|---|
| `No index in .index. Run: python -m backend.cli ingest` | No index has been built yet | Run `.venv/bin/python -m backend.cli ingest` (or pass a folder) |
| `Index was built with embedder 'X' but settings say 'Y'. Re-run ingest.` | `EMBED_PROVIDER` changed after ingest | Re-run ingest. Never mix vectors from two embedders |
| HTTP 403 `unknown user 'x'` | The user id isn't in `data/users.json` | Add the user on the server. Never let the client bypass this |
| HTTP 502 `AuthenticationError: ...` | The provider key is missing, wrong or expired | The owner fixes `.env`. Run `backend.cli doctor`, which shows set or not set and never the value |
| HTTP 503 `Users file not found` or `Data folder not found` | Wrong path in `.env`, or a relative path run from another folder | Fix `USERS_FILE` / `DATA_DIR`, or run from the project root |
| Every answer abstains | The relevance gate or guard is rejecting output, or the model isn't citing | Check `logs/traces.jsonl` for the reason and inspect the retrieved passages. Fix retrieval or the prompt, **not** the guard |
| `RULE CHECK FAILED` | A non-negotiable rule was broken | Fix the code at the `file:line` shown. Don't edit the checker to pass |

More cases are in `references/troubleshooting.md`.

## References (load only what the current step needs)
- `references/architecture.md`: components, data flow, API contract, trade-offs. Read in Step 3.
- `references/adapting-to-a-new-brief.md`: mapping a new brief, data and users onto the template. Read in Steps 1–3.
- `references/ingestion-and-chunking.md`: loaders per file type, chunk size and overlap, metadata. Read for M1.
- `references/retrieval.md`: BM25, embeddings, RRF hybrid, relevance gate, when to add reranking. Read for M1, M4 and M5.
- `references/generation-and-guardrails.md`: the prompt, passage wrapping, JSON parsing, the citation guard, refusals. Read for M1.
- `references/authorization.md`: the server-side model, deny by default, tests to write. Read for M2.
- `references/evaluation.md`: the golden-set format, metrics, regression baseline, confidence scores. Read for M3.
- `references/providers.md`: provider and model settings, the offline stub, the doctor check. Read in Step 2 or when switching models.
- `references/testing-and-ci.md`: the CI stages, unit vs regression tests, the commit flow. Read in Steps 2 and 5.
- `references/nextjs-supabase-variant.md`: porting the design to Next.js + Supabase pgvector, with a schema in `assets/supabase-schema.sql`. Read only if the owner asks for that stack.
- `references/troubleshooting.md`: the full error table.
- `references/resources.md`: official skills and RAG documentation links.

## Scripts
- `scripts/scaffold.py PROJECT_DIR [--no-sample]`: copies `assets/template/` (the tested app) into a new folder.
- `scripts/check_rules.py PROJECT_DIR [--require-approved-plan]`: deterministic checks of the critical rules. Exit code 1 lists violations as `file:line`.
