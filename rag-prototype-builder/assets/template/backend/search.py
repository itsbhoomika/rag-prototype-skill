"""Retrieval: index (BM25 + optional vectors) and search.

Basic retrieval is BM25 keyword search. Vector search is added on top only when
EMBED_PROVIDER is set (then results are fused with reciprocal rank fusion).
The authorization mask is applied inside each ranking, before any top-k cut: a chunk the
user may not see is never returned and never takes a result slot. Precisely: BM25 skips it,
and dense search scores every vector but sets forbidden ones to -inf before ranking. BM25
IDF/avgdl use the whole corpus (a ranking side effect, not a content leak; strict isolation
needs one index per access group). See the skill's references/retrieval.md.
"""
from __future__ import annotations

import json
import math
import re
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .ingest import Chunk
from .providers import Embedder

TOKEN = re.compile(r"[a-z0-9]+")
STOP = set(
    "a an and are as at be by for from has have how i in is it its of on or that the this to was what when "
    "where which who why will with do does can you your".split()
)
RRF_K = 60  # standard constant; avoids tuning weights between BM25 and cosine scores


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP]


@dataclass
class Hit:
    chunk: Chunk
    score: float                 # fused score
    bm25: float | None = None
    vector_sim: float | None = None


class Index:
    def __init__(self, chunks: list[Chunk], vectors: np.ndarray | None, embed_id: str):
        self.chunks = chunks
        self.vectors = vectors
        self.embed_id = embed_id
        self._build_bm25()

    def _build_bm25(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.lengths = np.zeros(len(self.chunks), dtype=np.float32)
        for i, c in enumerate(self.chunks):
            toks = tokenize(c.text)
            self.lengths[i] = len(toks)
            for term, tf in Counter(toks).items():
                self.postings[term].append((i, tf))
        n = len(self.chunks)
        self.avgdl = float(self.lengths.mean()) if n else 0.0
        self.idf = {t: math.log(1 + (n - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.postings.items()}

    def bm25(self, query: str, allowed: np.ndarray) -> list[tuple[int, float]]:
        scores = np.zeros(len(self.chunks), dtype=np.float32)
        for term in set(tokenize(query)):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i, tf in self.postings[term]:
                if allowed[i]:
                    denom = tf + self.k1 * (1 - self.b + self.b * self.lengths[i] / max(self.avgdl, 1e-9))
                    scores[i] += idf * tf * (self.k1 + 1) / denom
        return [(int(i), float(scores[i])) for i in np.argsort(-scores) if scores[i] > 0]

    def dense(self, qvec: np.ndarray, allowed: np.ndarray) -> list[tuple[int, float]]:
        sims = np.where(allowed, self.vectors @ qvec, -np.inf)
        return [(int(i), float(sims[i])) for i in np.argsort(-sims) if np.isfinite(sims[i])]

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "chunks.jsonl").write_text(
            "\n".join(json.dumps(asdict(c), ensure_ascii=False) for c in self.chunks), encoding="utf-8"
        )
        vec_path = directory / "vectors.npy"
        if self.vectors is not None:
            np.save(vec_path, self.vectors)
        elif vec_path.exists():
            vec_path.unlink()
        meta = {"embed_id": self.embed_id, "n_chunks": len(self.chunks), "built_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        (directory / "meta.json").write_text(json.dumps(meta, indent=2))

    @classmethod
    def load(cls, directory: Path) -> "Index":
        if not (directory / "meta.json").exists():
            raise FileNotFoundError(f"No index in {directory}. Run: python -m backend.cli ingest")
        meta = json.loads((directory / "meta.json").read_text())
        lines = (directory / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
        vec_path = directory / "vectors.npy"
        return cls([Chunk(**json.loads(l)) for l in lines if l.strip()],
                   np.load(vec_path) if vec_path.exists() else None, meta["embed_id"])


def allowed_mask(index: Index, filters: dict) -> np.ndarray:
    """filters = {"folder": ["policies", "support"]}; "*" in a list allows everything for that key.

    An empty filter dict means no restriction, so callers must pass the user's real filters
    (see backend/auth.py). The pipeline refuses to search with filters=None.
    """
    def ok(meta: dict) -> bool:
        for key, want in filters.items():
            wants = {str(w) for w in (want if isinstance(want, (list, tuple, set)) else [want])}
            if "*" in wants:
                continue
            have = meta.get(key)
            haves = {str(h) for h in (have if isinstance(have, (list, tuple, set)) else [have])}
            if not haves & wants:
                return False
        return True

    return np.array([ok(c.meta) for c in index.chunks], dtype=bool)


def search(index: Index, embedder: Embedder, query: str, filters: dict, k: int, candidates: int) -> list[Hit]:
    mask = allowed_mask(index, filters)
    rankings: list[tuple[str, list[tuple[int, float]]]] = [("bm25", index.bm25(query, mask)[:candidates])]
    if index.vectors is not None:
        # If the embedder fails, this raises. We never fall back to keyword-only silently.
        rankings.append(("vector_sim", index.dense(embedder.embed([query])[0], mask)[:candidates]))

    fused: dict[int, Hit] = {}
    for field, ranking in rankings:
        for rank, (i, raw) in enumerate(ranking):
            hit = fused.setdefault(i, Hit(index.chunks[i], 0.0))
            hit.score += 1.0 / (RRF_K + rank + 1)
            setattr(hit, field, raw)
    return sorted(fused.values(), key=lambda h: -h.score)[:k]
