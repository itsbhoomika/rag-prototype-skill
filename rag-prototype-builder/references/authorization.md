# Authorization

## The model
- The client sends **only** `user_id` (and the question).
- The server looks up the user in `data/users.json` (`backend/auth.py`). It turns the user's allowed folders into retrieval filters.
- The filters are applied inside each ranking, before any top-k cut (`search.allowed_mask`). See `retrieval.md` for exactly what this guarantees.
- The request model forbids extra fields (`extra="forbid"`), so `{"user_id": "bob", "filters": {"folder": ["*"]}}` gets a 422.
- `/api/users` returns ids and roles only. It never returns the folders.

## Defaults
| Case | Result |
|---|---|
| Unknown user id | `UnknownUser`, HTTP 403 |
| Known user, empty `allowed_folders` | sees nothing (deny by default; filter `["__none__"]`) |
| `"*"` in `allowed_folders` | all folders |
| Forbidden-only match for a question | relevance gate abstains: "no passages you can access matched the question" |

## What the UI may say about access
`searched_folders` lists the folders this user's search covered. `unsearched_folders` lists the other indexed folders, so the page can say "catalog isn't searched". That tells the user those folder names exist. If folder names are sensitive (for example `layoffs-2027`), set `SHOW_UNSEARCHED_FOLDERS=0` and record the choice in `PLAN.md`. Neither field ever carries another user's rules or any document text.

## Prototype limit (always state it)
**This is simulated identity, not access control against a real attacker.** The user id is taken on trust from the request, because there is no login: anyone who can reach the API can claim to be any user. The UI labels the picker as a simulation. Say this in the plan, the README and the final report. In production it comes from a verified session or token (SSO, JWT), and `filters_for()` stays the same. For a database-backed variant, add row-level security as a second layer (see `nextjs-supabase-variant.md`).

## Tests every brief needs (write them first, in M2)
1. For each user: a question that matches only a forbidden folder returns no passage from that folder, even though the query matches it exactly.
2. For each user: an allowed question retrieves from the allowed folder.
3. An unknown user gets 403 from the API.
4. Sending a `filters` field gets 422.
5. An eval question with `answerable: false` for a user asking about another group's document, scored as an abstention.

## Wrong patterns (`check_rules.py` catches the common ones)
- Accepting `filters`, `folders`, `groups` or `allowed_folders` in the request body.
- Filtering a top-k list after search.
- Putting folder lists in the frontend and trusting them.
- Logging passage text of records the user wasn't allowed to see.
