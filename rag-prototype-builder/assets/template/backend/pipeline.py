"""Orchestration: ingest() and ask(). The API, CLI and eval all call this."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from .auth import filters_for, load_users
from .config import Settings
from .generate import SYSTEM_PROMPT, Answer, build_user_prompt, guard, label_map
from .ingest import chunk_docs, load_corpus
from .providers import LLM, Embedder, LLMRefusal
from .search import Index, search


class RAG:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or Settings.from_env()
        self.llm = LLM(self.s)
        self.embedder = Embedder(self.s)
        self.users = load_users(self.s.users_file)
        self._index: Index | None = None

    # ---------------------------------------------------------------- ingest
    def ingest(self, data_dir: str | Path | None = None) -> dict:
        t0 = time.perf_counter()
        docs, skipped = load_corpus(data_dir or self.s.data_dir)
        chunks = chunk_docs(docs, self.s.chunk_size, self.s.chunk_overlap)
        t1 = time.perf_counter()
        vectors = self.embedder.embed([c.text for c in chunks]) if self.embedder.enabled and chunks else None
        t2 = time.perf_counter()
        self._index = Index(chunks, vectors, self.embedder.name)
        self._index.save(self.s.index_dir)
        return {
            "docs": len(docs),
            "chunks": len(chunks),
            "skipped_files": skipped,
            "folders": sorted({c.meta.get("folder", "") for c in chunks}),
            "embedder": self.embedder.name,
            "seconds": {"load_and_chunk": round(t1 - t0, 2), "embed": round(t2 - t1, 2)},
        }

    @property
    def index(self) -> Index:
        if self._index is None:
            index = Index.load(self.s.index_dir)
            if index.embed_id != self.embedder.name:
                raise RuntimeError(
                    f"Index was built with embedder '{index.embed_id}' but settings say '{self.embedder.name}'. "
                    "Re-run ingest."
                )
            self._index = index
        return self._index

    # ---------------------------------------------------------------- ask
    def ask(self, question: str, user_id: str) -> dict:
        """Authorization happens here, on the server: user id -> allowed filters -> search."""
        filters = filters_for(self.users, user_id)
        timings: dict[str, float] = {}

        t = time.perf_counter()
        hits = search(self.index, self.embedder, question, filters, self.s.top_k, self.s.candidates)
        timings["retrieve_ms"] = _ms(t)

        gate_reason = self._relevance_gate(hits)
        if gate_reason:
            ans = Answer("", [], True, gate_reason)
        else:
            t = time.perf_counter()
            try:
                raw = self.llm.complete(SYSTEM_PROMPT, build_user_prompt(question, hits))
            except LLMRefusal as e:  # a refusal is a real answer state, not a failure
                raw = json.dumps({"abstain": True, "reason": f"model refusal: {e}"})
            # Any other provider error propagates to the caller. No fake answer is produced.
            ans = guard(raw, hits)
            timings["generate_ms"] = _ms(t)

        labels = label_map(hits)
        result = {
            "question": question,
            "user_id": user_id,
            "answer": ans.text,
            "abstained": ans.abstained,
            "reason": ans.reason,
            "warnings": ans.warnings,
            "citations": [_hit_dict(lbl, labels[lbl]) for lbl in ans.citations],
            "retrieved": [_hit_dict(lbl, h) for lbl, h in labels.items()],
            "llm": self.llm.name,
            "llm_is_test_stub": self.llm.provider == "offline",
            "embedder": self.embedder.name,
            "timings": timings,
        }
        self._trace(result)
        return result

    def _relevance_gate(self, hits) -> str:
        if not hits:
            return "no passages you can access matched the question"
        if any(h.bm25 for h in hits):
            return ""
        top_sim = max((h.vector_sim for h in hits if h.vector_sim is not None), default=None)
        if top_sim is None or top_sim < self.s.min_vector_sim:
            return f"retrieved passages were not relevant enough (top similarity {top_sim})"
        return ""

    def _trace(self, result: dict) -> None:
        """One JSON line per request with ids and hashes, not passage text. Never breaks the request."""
        try:
            self.s.log_dir.mkdir(parents=True, exist_ok=True)
            row = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "user_id": result["user_id"],
                "question": result["question"],
                "abstained": result["abstained"],
                "reason": result["reason"],
                "cited": [c["chunk_id"] for c in result["citations"]],
                "retrieved": [(r["chunk_id"], r["score"]) for r in result["retrieved"]],
                "answer_sha1": hashlib.sha1(result["answer"].encode()).hexdigest()[:12],
                "llm": result["llm"],
                "timings": result["timings"],
            }
            with (self.s.log_dir / "traces.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
        except OSError as e:
            print(f"[trace] write failed: {e}")


def _hit_dict(label: str, hit) -> dict:
    return {
        "label": label,
        "chunk_id": hit.chunk.id,
        "source": hit.chunk.source,
        "section": hit.chunk.meta.get("section", ""),
        "page": hit.chunk.meta.get("page"),
        "text": hit.chunk.text,
        "score": round(hit.score, 4),
        "bm25": None if hit.bm25 is None else round(hit.bm25, 3),
        "vector_sim": None if hit.vector_sim is None else round(hit.vector_sim, 3),
    }


def _ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 1)
