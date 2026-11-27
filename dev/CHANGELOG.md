# Changelog

## 1.1.0 (2026-11-26)
Fixes from an independent review, each reproduced first:
- `--no-sample` projects failed CI (13 errors): tests now use `tests/fixtures/`; the scaffold copies fixtures into `data/` only for the sample path. Owner questions get their own regression gate (`tests/data_baseline.json`).
- `./ci.sh --live` passed with the offline stub and 4 failed items: live now runs `doctor --require-real` and `eval --strict`.
- The guard crashed on wrong-shape JSON and accepted invented numbers that cited a real passage: it now checks shape and that every number appears in a cited passage.
- `judge_accuracy` ignored abstentions: an abstention on an answerable question now counts as incorrect.
- Wording: the access mask's exact guarantee (dense scores everything then masks; BM25 statistics are corpus-wide) and simulated identity are stated in code, docs and UI.
- Gemini default `gemini-2.5-flash` (deprecated) -> `gemini-3.5-flash`.
- SKILL.md reorganised into three paths (sample, new build, improve); body 1,614 -> about 1,240 words. Access rules and a small golden set moved into M1. Plan approval can be given in chat. `project-manager` agent made optional and cut from 491 to 200 words.

Versions match `metadata.version` in `rag-prototype-builder/SKILL.md`.

## 1.0.0 (2026-11-26)
- First release: SKILL.md workflow with validation gates, 12 reference files, `scaffold.py`, `check_rules.py`.
- Bundled template: the tested FastAPI + one-page RAG prototype (26 offline tests, local CI).
- Next.js + Supabase pgvector variant notes and schema (schema not yet run against a live database).
- Repo tooling: guide-based validator, packager, template functional test, triggering tests.
