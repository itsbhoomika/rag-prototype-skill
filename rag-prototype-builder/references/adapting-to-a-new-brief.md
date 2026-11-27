# Adapting the template to a new brief

The template works on fictional shop data (policies, support, catalog). For a new brief, change the **data, users and questions** first. Change code only where the brief needs a behaviour the template lacks.

## 1. Map the brief
Fill this in before writing `PLAN.md`:

| Question | Where it goes |
|---|---|
| What documents, which file types? | `data/sample/` (or set `DATA_DIR`), one top-level folder per access group |
| Who are the users, what may each see? | `data/users.json`: `{"users": {"id": {"role": "...", "allowed_folders": ["folder", ...]}}}`. `"*"` means all folders |
| What questions must it answer? | `data/questions.jsonl` (see `evaluation.md`) |
| Which provider and key? | `.env` (the owner fills it in), `references/providers.md` |
| Sensitive data? | The privacy risks section of `PLAN.md` |

## 2. Folders are the access unit
Authorization works on the **top-level folder** of each file, stored as `meta["folder"]` at ingest. So arrange the data by who may see it:
```
data/sample/
  hr-only/        salaries.csv
  all-staff/      handbook.pdf, holidays.md
```
If access depends on something other than folders (for example a per-record owner or department), add that field to the chunk metadata at ingest. Extend `filters_for()` and `allowed_mask()` to match it, and write the tests from `authorization.md` first.

## 3. File types
Supported: `.md`, `.txt`, `.pdf` (one Doc per page), `.csv` and `.json` (one `column: value` record per row), `.html`.

Unsupported files are skipped and listed in the ingest output, so report them to the owner. To add a type (for example `.docx`):
1. Add a loader branch in `_load_file()`.
2. Add the suffix to `SUPPORTED`.
3. Add a unit test with a tiny fixture file.

## 4. Sensitive domains (medical, legal, HR, finance)
- Use synthetic data unless the owner confirms that real data is allowed with their chosen provider. Fictional identifiers should look fictional, for example `MRN-SYN-0001`.
- Add the risks to `PLAN.md`:
  - data sent to a third-party model API
  - logs (the trace stores ids and hashes, not text)
  - authorization gaps
  - prompt injection inside documents
- Add golden questions where the right answer is to abstain, for example questions about a record the user may not see.

## 5. What not to change
- Don't remove the guard, the passage wrapping, `extra="forbid"` or the stub label to make something "work".
- Don't add a database, a queue or a second service unless `PLAN.md` gives a reason (scale, concurrency, persistence) that the in-memory index can't meet.

## 6. Plan template answers
- **Milestones:** start from the default M1–M5 table in `SKILL.md`. Rename them for the brief.
- **Assumptions:** write each as `ASSUMPTION: ...` so the owner can accept or reject it.
- **Not implemented:** always list login/SSO, reranking (until measured), hosted deployment, and anything the brief mentioned that the plan defers.
