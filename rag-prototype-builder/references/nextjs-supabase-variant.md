# Variant: Next.js + Supabase (pgvector)

Use this only if the owner asks for a TypeScript stack or a hosted database. The Python template stays the tested reference. Port the design, not the shortcuts.

## Module mapping
| Python template | Next.js variant |
|---|---|
| `backend/config.py` | `src/lib/config.ts` (reads `process.env`, validated with zod) |
| `backend/ingest.py` | `scripts/ingest.ts` (run with `npx tsx`). Same loaders and chunk rules |
| `backend/search.py` | `src/lib/search.ts`: calls `match_chunks` and `match_chunks_fts` and fuses them with RRF (k=60) in code |
| `backend/generate.py` | `src/lib/generate.ts`: same system prompt, passage wrapping, `guard()` |
| `backend/auth.py` | `src/lib/auth.ts`: user id → groups, from a server-side JSON file or a `users` table |
| `backend/providers.py` | `src/lib/providers.ts`: `@google/genai`, `@anthropic-ai/sdk`; offline stub labelled |
| `backend/api.py` | `src/app/api/ask/route.ts`: zod `.strict()` schema, so extra fields get 422 |
| `frontend/` | `src/app/page.tsx`: React escapes by default. Never use `dangerouslySetInnerHTML` |
| `tests/` | Vitest, with the same cases |

## Database
Apply `assets/supabase-schema.sql` once in the Supabase SQL editor. It creates:
- `documents` and `chunks` tables, with `allowed_groups text[]` on each chunk
- an HNSW index on `embedding` (cosine), plus GIN indexes on the groups and the full-text column
- `match_chunks(query_embedding, user_groups, match_count)` for dense search, filtered by group overlap **inside the query**
- `match_chunks_fts(query_text, user_groups, match_count)` for keyword search with the same filter

The vector size (768) must match the embedding model. Change both together.

With strict filters, an HNSW search can return fewer than `match_count` rows. Raise `match_count` (or the `hnsw.ef_search` setting) if eval shows missing results for small groups.

## Rules that carry over unchanged
- The client sends only `userId` and `question`. Groups come from the server. The zod schema is `.strict()`.
- The Supabase **service-role key** bypasses row-level security. Use it only in server code. Never send it to the browser, and never use a `NEXT_PUBLIC_` variable for it.
- Embedding or database failure returns 502 with the error, never a keyword-only or cached result.
- Cite-or-abstain guard, passage wrapping and the relevance gate, as in the Python version.
- Row-level security with Supabase Auth is the production second layer. The SQL functions are the first layer.

## Verification
- `doctor` script: checks that the env vars are set (never prints them), that the `match_chunks` function exists, and makes one tiny call to each model.
- A database test with two throwaway rows in different groups proves `match_chunks` never returns the other group's row. Delete the rows afterwards.

Status: the schema file is provided but hasn't been run against a live database in this skill's CI. Treat its first run as a milestone with evidence.
