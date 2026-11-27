"""LLM and embedding adapters. Pick with LLM_PROVIDER / EMBED_PROVIDER.

Two SDKs cover every provider:
- anthropic SDK  -> Claude
- openai SDK     -> OpenAI, Azure OpenAI, Gemini (OpenAI-compatible endpoint), Ollama
SDKs are imported lazily so you only install what you use.
"""
from __future__ import annotations

import json
import os
import re

import numpy as np

from .config import Settings

DEFAULT_LLM = {
    "anthropic": "claude-opus-5-5",
    "openai": "gpt-4.1-mini",        # set LLM_MODEL to whatever the key allows
    "azure": "",                      # uses AZURE_OPENAI_DEPLOYMENT
    "gemini": "gemini-2.5-flash",     # verify at session start
    "ollama": "llama3.2:3b",
    "offline": "extractive-stub",
}
DEFAULT_EMBED = {
    "openai": "text-embedding-3-small",
    "azure": "",                      # uses AZURE_OPENAI_EMBED_DEPLOYMENT
    "gemini": "gemini-embedding-001",
    "ollama": "nomic-embed-text",
    "local": "BAAI/bge-small-en-v1.5",
    "none": "",
}
GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Which env vars each provider needs (doctor reports set / not set, never values).
REQUIRED_ENV = {
    "anthropic": ["ANTHROPIC_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "azure": ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"],
    "gemini": ["GEMINI_API_KEY"],
    "ollama": [],
    "offline": [],
    "local": [],
    "none": [],
}


class LLMRefusal(RuntimeError):
    pass


# ---------------------------------------------------------------- clients
def _openai_compatible(provider: str):
    from openai import AzureOpenAI, OpenAI

    if provider == "openai":
        return OpenAI()
    if provider == "gemini":
        return OpenAI(api_key=os.environ["GEMINI_API_KEY"], base_url=GEMINI_OPENAI_BASE)
    if provider == "ollama":
        return OpenAI(api_key="ollama", base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"))
    if provider == "azure":
        return AzureOpenAI(
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        )
    raise ValueError(f"not an OpenAI-compatible provider: {provider}")


# ---------------------------------------------------------------- LLMs
class LLM:
    def __init__(self, settings: Settings):
        self.provider = settings.llm_provider
        if self.provider not in DEFAULT_LLM:
            raise ValueError(f"Unknown LLM_PROVIDER '{self.provider}'. Options: {', '.join(DEFAULT_LLM)}")
        self.model = settings.llm_model or DEFAULT_LLM[self.provider]
        if self.provider == "azure":
            self.model = settings.llm_model or os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
        self.settings = settings
        self._client = None

    @property
    def name(self) -> str:
        return f"{self.provider}:{self.model}"

    def complete(self, system: str, user: str) -> str:
        if self.provider == "offline":
            return _offline_answer(user)
        if self.provider == "anthropic":
            return self._anthropic(system, user)
        if self._client is None:
            self._client = _openai_compatible(self.provider)
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        return resp.choices[0].message.content or ""

    def _anthropic(self, system: str, user: str) -> str:
        import anthropic

        if self._client is None:
            self._client = anthropic.Anthropic()
        kwargs = dict(
            model=self.model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": self.settings.claude_effort},
        )
        if self.settings.claude_fallbacks:
            # Server-side refusal fallback: the API re-runs a declined request on a fallback model.
            # Turn off with CLAUDE_FALLBACKS=0 (e.g. behind a proxy that rejects beta fields).
            resp = self._client.beta.messages.create(
                **kwargs, betas=["server-side-fallback-2026-07-01"], extra_body={"fallbacks": "default"}
            )
        else:
            resp = self._client.messages.create(**kwargs)
        if resp.stop_reason == "refusal":
            raise LLMRefusal("model declined the request")
        return "".join(block.text for block in resp.content if block.type == "text")


def _offline_answer(user_prompt: str) -> str:
    """Deterministic stand-in so the pipeline and tests run with no keys.

    Picks the passage with the most question-word overlap and quotes its first
    sentence. Abstains when overlap is weak. Not a quality signal.
    """
    question = user_prompt.rsplit("Question:", 1)[-1]
    q_words = {w for w in re.findall(r"[a-z0-9]+", question.lower()) if len(w) > 3}
    best, best_score = None, 0.0
    for label, body in re.findall(r'<passage id="(P\d+)"[^>]*>\n(.*?)\n</passage>', user_prompt, re.S):
        words = set(re.findall(r"[a-z0-9]+", body.lower()))
        score = len(q_words & words) / max(len(q_words), 1)
        if score > best_score:
            best, best_score = (label, body), score
    if not best or best_score < 0.5:
        return json.dumps({"answer": "", "citations": [], "abstain": True, "reason": "offline stub: weak overlap"})
    label, body = best
    first = re.split(r"(?<=[.!?])\s+", " ".join(body.split()))[0][:300]
    return json.dumps({"answer": f"{first} [{label}]", "citations": [label], "abstain": False, "reason": ""})


# ---------------------------------------------------------------- embeddings
class Embedder:
    def __init__(self, settings: Settings):
        self.provider = settings.embed_provider
        if self.provider not in DEFAULT_EMBED:
            raise ValueError(f"Unknown EMBED_PROVIDER '{self.provider}'. Options: {', '.join(DEFAULT_EMBED)}")
        self.model = settings.embed_model or DEFAULT_EMBED[self.provider]
        if self.provider == "azure":
            self.model = settings.embed_model or os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "")
        self._client = None

    @property
    def enabled(self) -> bool:
        return self.provider != "none"

    @property
    def name(self) -> str:
        return f"{self.provider}:{self.model}" if self.enabled else "none"

    def embed(self, texts: list[str], batch_size: int = 64) -> np.ndarray:
        if not self.enabled:
            raise RuntimeError("embeddings disabled (EMBED_PROVIDER=none)")
        if self.provider == "local":
            from sentence_transformers import SentenceTransformer

            if self._client is None:
                self._client = SentenceTransformer(self.model)
            vecs = self._client.encode(texts, batch_size=batch_size, normalize_embeddings=True)
            return np.asarray(vecs, dtype=np.float32)
        if self._client is None:
            self._client = _openai_compatible(self.provider)
        out: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            resp = self._client.embeddings.create(model=self.model, input=texts[i : i + batch_size])
            out.extend(d.embedding for d in resp.data)
        vecs = np.asarray(out, dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / np.maximum(norms, 1e-12)
