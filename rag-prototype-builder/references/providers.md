# Providers

All settings live in `.env`. The owner fills it in from `.env.example`. Never read, print or ask for key values.

## LLM (`LLM_PROVIDER`)
| Provider | Default model (`LLM_MODEL` overrides) | Needs |
|---|---|---|
| `anthropic` | `claude-opus-5-5` | `ANTHROPIC_API_KEY` |
| `openai` | `gpt-4.1-mini` | `OPENAI_API_KEY` |
| `azure` | the deployment name | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT` |
| `gemini` | `gemini-2.5-flash` (via the OpenAI-compatible endpoint) | `GEMINI_API_KEY` |
| `ollama` | `llama3.2:3b` | a local Ollama at `OLLAMA_BASE_URL` |
| `offline` | `extractive-stub` | nothing. A **test stub**, labelled `llm_is_test_stub: true` in the API, CLI and UI |

Model names change. Run `doctor` at the start of a session and set `LLM_MODEL` to what the key allows.

### Claude specifics
- `CLAUDE_EFFORT` (`low` / `medium` / `high`) trades speed for care. `low` is fine for short cited answers.
- `CLAUDE_FALLBACKS=1` sends the server-side refusal-fallback beta. Set it to `0` if a proxy rejects that beta.
- A `refusal` stop reason raises `LLMRefusal`. The pipeline turns it into an abstention.

## Embeddings (`EMBED_PROVIDER`)
| Provider | Default model | Notes |
|---|---|---|
| `none` | — | BM25 only. The default, and an explicit choice |
| `openai` | `text-embedding-3-small` | |
| `azure` | the deployment | `AZURE_OPENAI_EMBED_DEPLOYMENT` |
| `gemini` | `gemini-embedding-001` | |
| `ollama` | `nomic-embed-text` | local |
| `local` | `BAAI/bge-small-en-v1.5` | needs `sentence-transformers` (about 1 GB download, so ask before installing) |

Changing the embedder requires re-running ingest. The index refuses mismatched vectors.

## Doctor
```bash
.venv/bin/python -m backend.cli doctor
```
`doctor` reports each needed env var as set or not set, never its value. It then makes one tiny live call per configured provider and prints success or the real error.

## The offline stub
The stub exists so tests and CI run deterministically with no keys. It picks the passage with the most question-word overlap and quotes that passage's first sentence, with a citation. If the overlap is weak, it abstains.

It is never a fallback. If a real provider fails, the request fails with 502. Switching to `offline` is something the owner does explicitly in `.env`.
