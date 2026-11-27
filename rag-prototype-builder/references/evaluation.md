# Evaluation

## Golden set (`data/questions.jsonl`)
One JSON object per line:
```json
{"id": "q1", "question": "What is the return window for kayaks?", "answerable": true, "user_id": "admin", "expected_sources": ["returns.md"], "expected_answer": "30 days from delivery"}
```
- `expected_sources` matches against chunk ids by substring (file name or `file::n`).
- Include, for a brief, roughly 10–30 questions:
  - answerable questions across every file type
  - paraphrased questions (to test whether embeddings are needed)
  - questions with no answer in the data (`answerable: false`)
  - **authorization questions**: a user asking about a folder they can't see (`answerable: false`)

## Run
```bash
.venv/bin/python -m backend.cli eval --label baseline
.venv/bin/python -m backend.cli eval --label hybrid --judge   # --judge adds LLM-graded correctness (costs calls)
```
Each run saves its metrics and per-question rows in `eval_runs/`, so runs can be compared.

## Metrics
| Metric | Meaning | Measures |
|---|---|---|
| `hit@k` (retrieval@k) | share of answerable questions where an expected source is in the top k | search recall |
| `mrr` | mean of 1/rank of the first expected source | search ranking |
| `citation_hit` | the answer cites an expected source | end to end, grounded answers |
| `abstain_recall` | share of unanswerable questions that abstained | safety: doesn't make things up |
| `abstain_precision` | share of abstentions that were truly unanswerable | usefulness: doesn't over-abstain |
| `judge_accuracy` | LLM judge says the answer matches `expected_answer` | answer correctness (live only) |
| `latency_p50_ms` | median request time | cost and UX |

Always report the item count with a metric. "hit@k 1.0 on 11 questions" isn't the same as on 200.

### Adding precision@k
Precision@k is the share of the top k retrieved chunks that come from an expected source. It shows how much noise reaches the prompt. To add it:
1. In `score_item`, compute `sum(_matches(cid, expected) for cid in ids[:k]) / k`.
2. Average it in `summarize`.
3. Add a unit test with fixed retrieved ids.

## Regression baseline
`tests/test_regression.py` runs the golden set offline (keyword search + stub) and compares the results with `tests/regression_baseline.json`. Any metric below the baseline fails CI.

Update the baseline only when a metric improved on purpose, or when the question set changed:
```bash
UPDATE_BASELINE=1 .venv/bin/python -m pytest tests/test_regression.py
```
Never update it to turn a red build green.

## Reading offline numbers honestly
Offline, `hit@k` and `mrr` are real search signals. `citation_hit` and the abstention metrics pass through the stub, so they catch plumbing breaks (guard, gate, wiring), not answer quality. Quality comes from `./ci.sh --live` and `--judge`.
