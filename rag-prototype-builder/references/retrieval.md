# Retrieval

## Order of features (rule 6)
1. **BM25 keyword search.** Always on. Deterministic, no keys, strong on exact terms (product names, codes, IDs).
2. **Embeddings (dense) + RRF hybrid.** Turn these on only after an eval baseline shows misses on paraphrased questions.
3. **Reranking.** Add it only after hybrid is measured and eval shows the right passage is retrieved but ranked low (good `hit@k`, weak `mrr`).

Record every step as an eval run with a label (`baseline`, `hybrid`, `rerank`). Keep a step only if it improved a metric.

## Filter before scoring
`allowed_mask(index, filters)` returns a boolean mask over all chunks. It is built from the server-side filters (`{"folder": [...]}`, where `"*"` means all).

The mask is applied inside each ranking, before any top-k cut. What that guarantees, exactly:
- A forbidden chunk never appears in the results, never reaches the prompt and never takes a slot in the top k.
- BM25 adds term scores only for masked-in chunks.
- Dense search computes the dot product for every vector, then sets forbidden ones to minus infinity before ranking. The forbidden scores are discarded, never returned or logged.

What it does **not** guarantee: BM25 word statistics (IDF and average length) come from the whole corpus, so forbidden documents slightly shift the scores of allowed ones. That is a ranking side effect, not a content leak, and it is fine for a prototype. Strict isolation needs one index per access group (or per-group statistics).

Filtering a top-k list after retrieval is wrong. It returns fewer than k results, and the forbidden passages have already been ranked and may get logged.

## BM25
Standard Okapi BM25 (`k1=1.5`, `b=0.75`) over lowercase word tokens. Postings are built at ingest and saved in `.index/`.

## Embeddings
- Enable them with `EMBED_PROVIDER` (`openai`, `azure`, `gemini`, `ollama` or `local`). The owner sets this in `.env`.
- Vectors are L2-normalised, so cosine similarity is a dot product.
- The index stores `embed_id` (provider + model). Loading an index built with a different embedder raises "Re-run ingest". Never compare vectors from two models.
- If the embedder fails at query time, **the error propagates**. Never fall back to BM25-only silently (rule 3). The owner may choose `EMBED_PROVIDER=none` explicitly.

## Hybrid fusion: Reciprocal Rank Fusion
For each chunk, `score = sum over rankings of 1 / (60 + rank)`. RRF uses ranks, not raw scores, so BM25 and cosine (different scales) need no weight tuning. The constant 60 is the standard value. `CANDIDATES` (default 30) is how many results each ranking contributes before fusion. `TOP_K` (default 6) is how many go to the prompt.

## Relevance gate (`pipeline._relevance_gate`)
The gate abstains before calling the model when:
- no allowed passage matched, or
- there is no BM25 match and the best vector similarity is below `MIN_VECTOR_SIM` (default 0.25).

This saves a model call and stops the model answering from unrelated text.

## Reranking (only when measured)
If eval shows a ranking problem:
1. Rerank the fused top `CANDIDATES` with a cross-encoder or an LLM reranker. Return the top `TOP_K`.
2. Keep the authorization mask unchanged. Rerank only allowed chunks.
3. A reranker failure raises. It never silently returns the un-reranked list.
4. Run eval with `--label rerank`, then compare `mrr` and latency.

## Tests to keep or add
- A user never retrieves a chunk outside their folders, even when the query matches it exactly.
- An unknown user raises.
- A user with no folders sees nothing (deny by default).
- An embedder failure raises instead of returning keyword results.
- An embed-id mismatch raises "Re-run ingest".
