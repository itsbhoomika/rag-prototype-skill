# Architecture

## Contents
- Components
- Request flow
- API contract
- Trace log
- Trade-offs (say these out loud when explaining the build)

## Components
One Python backend, one HTML page. Each component is a module with one job, so it can be tested and swapped on its own.

| Module | Job | Key function |
|---|---|---|
| `backend/config.py` | Settings from `.env`, with defaults | `Settings.from_env()` |
| `backend/ingest.py` | files → `Doc` → `Chunk` | `load_corpus()`, `chunk_docs()` |
| `backend/search.py` | BM25 + optional dense vectors, filter before scoring, RRF fusion | `allowed_mask()`, `search()` |
| `backend/generate.py` | prompt with wrapped passages, JSON parse, citation guard | `build_user_prompt()`, `guard()` |
| `backend/auth.py` | user id → allowed folders (server side) | `filters_for()` |
| `backend/providers.py` | LLM and embedding adapters; `offline` test stub | `LLM.complete()`, `Embedder.embed()` |
| `backend/pipeline.py` | orchestrates ingest and ask; writes the trace | `RAG.ingest()`, `RAG.ask()` |
| `backend/evaluate.py` | golden questions → metrics → `eval_runs/` | `run()` |
| `backend/api.py` | FastAPI endpoints, error mapping, serves `frontend/` | `/api/ask` |
| `backend/cli.py` | `doctor`, `ingest`, `ask --user`, `eval` | |
| `frontend/` | `index.html` + `app.js`, no build step, no CDN | `textContent` only |

## Request flow (`RAG.ask(question, user_id)`)
1. `filters_for(users, user_id)` turns the user id into folder filters. An unknown user raises `UnknownUser`, which the API maps to HTTP 403.
2. `search()`:
   - `allowed_mask()` marks the chunks this user may see.
   - BM25 (and cosine, if embeddings are on) scores only those chunks.
   - The two rankings are fused with RRF, and the top `TOP_K` are kept.
3. The relevance gate abstains if nothing matched, or if the vectors alone are below `MIN_VECTOR_SIM`.
4. `build_user_prompt()` wraps each passage with a label `P1..Pn` and its source, and escapes tag breakout.
5. `LLM.complete(SYSTEM_PROMPT, prompt)` runs:
   - A refusal becomes an abstention with the reason "model refusal".
   - Any other provider error propagates. The API maps it to HTTP 502, and no answer is invented.
6. `guard()` parses the JSON, keeps only citations that point at retrieved labels, and abstains if none are left.
7. The result returns the answer, citations, retrieved passages, `llm_is_test_stub` and timings. A trace line is written.

## API contract
`POST /api/ask`

Request: `{"user_id": str (1–64), "question": str (1–2000)}`. The request model sets `extra="forbid"`, so any other field (for example `filters`) gets a 422.

Response fields:
- `answer`, `abstained`, `reason`, `warnings[]`
- `numbers_checked`: numbers in the answer, each found in a cited passage by the guard (the UI's "every number found" line)
- `searched_folders[]`: folders this user's search covered. `unsearched_folders[]`: indexed folders they can't search (empty when `SHOW_UNSEARCHED_FOLDERS=0`; see `authorization.md`)
- `ignored_instructions[]`: retrieved passages that talk to the model, each `{label, source, quote, cited}` (see `generation-and-guardrails.md`)
- `citations[]` and `retrieved[]`. Each item has `label`, `chunk_id`, `doc_id`, `position` (order within its document), `source`, `section`, `page`, `text`, `score`, `bm25`, `vector_sim`.
- `llm`, `llm_is_test_stub`, `embedder`, `timings`

## The page (Reader layout)
One page, two panes. Left: the question, an access line built from `searched_folders` / `unsearched_folders`, a facts line (passages cited, `numbers_checked`), the answer with each `[P#]` turned into a marker, the instruction notice, and "Also searched, not used" collapsed. Right: the sources, rebuilt only from retrieved chunks in `position` order with gaps marked "not retrieved", the cited passage highlighted. Clicking a marker opens its passage, underlines the text before the marker and moves keyboard focus to the passage. On a phone the right pane is a bottom sheet (Escape or Close returns focus to the marker). Designed states: welcome, loading, answer, no answer, error, test mode, server down, nothing indexed. The page never fetches whole files: that would need its own permission-checked endpoint.

Errors:
- 403: unknown user
- 422: bad or extra fields
- 503: index or data missing
- 502: provider failure, with the error type shown

`GET /api/health` returns the LLM name, `llm_is_test_stub`, the embedder name and the index chunk count.

`GET /api/users` returns ids and roles only, never the folders, for the user picker.

## Trace log
`logs/traces.jsonl` gets one line per request, with:
- the user id and question
- abstained and reason
- cited and retrieved chunk ids with their scores
- a hash of the answer
- timings

It never stores passage text, so the log doesn't copy document content. A failed trace write prints a warning and never breaks the request.

## Trade-offs (say these out loud when explaining the build)
| Choice | Why | Cost / when to change |
|---|---|---|
| In-memory BM25 + numpy vectors, saved in `.index/` | No database to set up. Deterministic tests. Fast for a few thousand chunks | Move to pgvector or another vector store past roughly 100k chunks, or when several processes write at once |
| RRF fusion | No weight tuning between BM25 and cosine scores, which aren't on the same scale | Learned or weighted fusion only if eval shows RRF is the bottleneck |
| Filter before scoring | A forbidden chunk can never rank, leak into the prompt or affect scores | None. Filtering after retrieval is a security bug |
| User picker instead of login | Keeps the prototype small | Production takes the user id from a verified session (SSO/JWT) |
| JSON output + guard | Citations can be checked by code, and the model can't cite a passage it wasn't given | Some valid answers abstain when the model formats badly. Fix the prompt, not the guard |
| Offline stub | Deterministic CI with no keys | It measures plumbing, not answer quality. Use `./ci.sh --live` for quality |
| One page, no build step | Nothing to install for the UI. Easy to audit escaping | Move to a framework only if `PLAN.md` needs richer UI |
