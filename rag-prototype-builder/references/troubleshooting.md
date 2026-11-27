# Troubleshooting

## Setup
| Symptom | Cause | Solution |
|---|---|---|
| `No .venv. Run: uv venv && uv pip install -r requirements.txt` (from `ci.sh`) | Environment not created | Run the command shown. Without `uv`: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` |
| `ERROR: ... is not empty` (scaffold) | The target folder already has files | Pick an empty folder. The script never overwrites |
| `Template not found` (scaffold) | The skill folder was copied without `assets/` | Re-install the whole skill folder |
| `ModuleNotFoundError: backend` | Tests run from the wrong folder | Run from the project root. `pytest.ini` sets `pythonpath = .` |

## Runtime
| Symptom | Cause | Solution |
|---|---|---|
| `No index in .index. Run: python -m backend.cli ingest` | Not ingested | Run ingest |
| `Index was built with embedder 'X' but settings say 'Y'. Re-run ingest.` | The embedder changed | Re-run ingest |
| `Data folder not found: ...` | Wrong `DATA_DIR`, or a relative path from another folder | Fix `.env`, or run from the project root |
| `Users file not found: ...` | Wrong `USERS_FILE` | Same as above |
| 403 `unknown user` | The id isn't in `users.json` | Add the user on the server |
| 422 on `/api/ask` | Extra or invalid field (for example `filters`) | Expected. Send only `user_id` and `question` |
| 502 `AuthenticationError` / `NotFoundError` | Bad key, or a model name the key can't use | Owner fixes `.env`. Run `doctor`. Set `LLM_MODEL` |
| 502 `RuntimeError: embeddings disabled` | Code asked for vectors while `EMBED_PROVIDER=none` | Set an embed provider and re-ingest, or keep BM25 only by choice |
| UI shows the yellow "test stub" banner | `LLM_PROVIDER=offline` | Expected in tests. Set a real provider for real answers |

## Quality
| Symptom | Likely cause | Fix (never weaken the guard) |
|---|---|---|
| Many abstentions with "answer had no valid citation" | The model doesn't follow the citation format | Check the raw output in a test. Tighten the prompt with an example. Check the model's JSON ability |
| "retrieved passages were not relevant enough" | Vector-only match below `MIN_VECTOR_SIM` | Check the query and embedder. Tune the threshold with eval, not by eye |
| Right doc retrieved but answer missing | The chunk is too large or split badly | Tune `CHUNK_SIZE`/`CHUNK_OVERLAP`, re-ingest, run eval |
| Misses on paraphrases | BM25 only | Enable embeddings (M4), measure |
| Good `hit@k`, weak `mrr` | Ranking problem | Consider reranking (M5), measure |
| Regression stage fails after a change | A metric dropped | Find which question changed in `eval_runs/`. Fix the cause. Update the baseline only if the drop was intended and explained |

## Skill behaviour
| Symptom | Fix |
|---|---|
| The skill doesn't load for a RAG request | Ask Claude "When would you use the rag-prototype-builder skill?" Add the user's wording to the description triggers |
| The skill loads for unrelated LLM work | Strengthen the negative triggers in the description |
| Steps get skipped | Point Claude at the gate of the current step. Run `check_rules.py` |
