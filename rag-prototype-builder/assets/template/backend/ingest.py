"""Ingestion: files -> Docs -> Chunks.

Loaders: md/txt, pdf (one Doc per page), csv/tsv and json (rows as 'column: value'), html.
Unknown file types are reported as skipped, never silently dropped.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path


@dataclass
class Doc:
    id: str
    source: str              # path relative to the data folder
    text: str
    meta: dict = field(default_factory=dict)


@dataclass
class Chunk:
    id: str                  # "<doc id>::<n>"
    doc_id: str
    source: str
    text: str                # indexed and shown; includes section/table context line
    meta: dict = field(default_factory=dict)


TEXT_TYPES = {".md", ".markdown", ".txt", ".rst"}
SUPPORTED = TEXT_TYPES | {".pdf", ".csv", ".tsv", ".json", ".jsonl", ".html", ".htm"}


# ---------------------------------------------------------------- loading
def load_corpus(root: str | Path) -> tuple[list[Doc], list[str]]:
    """Return (docs, skipped_files). meta['folder'] is the top-level folder, used for authorization."""
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"Data folder not found: {root}")
    docs: list[Doc] = []
    skipped: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        rel = path.relative_to(root).as_posix()
        if path.suffix.lower() not in SUPPORTED:
            skipped.append(rel)
            continue
        base = {"source": rel, "folder": rel.split("/")[0] if "/" in rel else "", "type": path.suffix.lower().lstrip(".")}
        for doc in _load_file(path, rel):
            doc.meta = {**base, **doc.meta}
            if doc.text.strip():
                docs.append(doc)
    return docs, skipped


def _load_file(path: Path, rel: str) -> list[Doc]:
    suffix = path.suffix.lower()
    if suffix in TEXT_TYPES:
        return [Doc(rel, rel, _read(path), {"kind": "markdown" if suffix in {".md", ".markdown"} else "text"})]
    if suffix == ".pdf":
        from pypdf import PdfReader

        return [
            Doc(f"{rel}#page-{i}", rel, page.extract_text() or "", {"kind": "text", "page": i})
            for i, page in enumerate(PdfReader(str(path)).pages, start=1)
        ]
    if suffix in {".csv", ".tsv"}:
        with path.open(newline="", encoding="utf-8", errors="replace") as f:
            rows = [_record(r) for r in csv.DictReader(f, delimiter="\t" if suffix == ".tsv" else ",")]
        return [Doc(rel, rel, "\n".join(rows), {"kind": "records"})]
    if suffix in {".json", ".jsonl"}:
        raw = _read(path)
        data = [json.loads(l) for l in raw.splitlines() if l.strip()] if suffix == ".jsonl" else json.loads(raw)
        if isinstance(data, dict):
            lists = [v for v in data.values() if isinstance(v, list) and v and isinstance(v[0], dict)]
            data = lists[0] if lists else data
        if isinstance(data, list) and data and all(isinstance(x, dict) for x in data):
            rows = [_record({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in r.items()}) for r in data]
            return [Doc(rel, rel, "\n".join(rows), {"kind": "records"})]
        return [Doc(rel, rel, json.dumps(data, indent=2, ensure_ascii=False), {"kind": "text"})]
    if suffix in {".html", ".htm"}:
        return [Doc(rel, rel, _html_to_text(_read(path)), {"kind": "text"})]
    return []


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _record(row: dict) -> str:
    """'column: value; column: value' keeps every value next to its header."""
    return "; ".join(f"{k}: {v}" for k, v in row.items() if v not in (None, ""))


class _TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self._skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")
        if tag in {"h1", "h2", "h3"}:
            self.parts.append("#" * int(tag[1]) + " ")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    lines = [" ".join(l.split()) for l in "".join(parser.parts).splitlines()]
    return "\n".join(l for l in lines if l)


# ---------------------------------------------------------------- chunking
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def chunk_docs(docs: list[Doc], size: int = 1200, overlap: int = 150) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in docs:
        kind = doc.meta.get("kind")
        if kind == "records":
            pieces = [(f"Records from {doc.source}", p) for p in _pack(doc.text.splitlines(), size, 0)]
        elif kind == "markdown":
            pieces = [(h, p) for h, body in _sections(doc.text) for p in _pack(_paragraphs(body), size, overlap)]
        else:
            pieces = [("", p) for p in _pack(_paragraphs(doc.text), size, overlap)]
        for n, (heading, body) in enumerate(pieces):
            text = f"{heading}\n{body}" if heading else body
            chunks.append(Chunk(f"{doc.id}::{n}", doc.id, doc.source, text.strip(), {**doc.meta, "section": heading}))
    return [c for c in chunks if c.text]


def _sections(text: str) -> list[tuple[str, str]]:
    """Split markdown on headings; keep the heading path ('Returns > Kayaks') as context."""
    path: list[str] = []
    sections: list[tuple[str, list[str]]] = [("", [])]
    for line in text.splitlines():
        m = HEADING.match(line)
        if m:
            path = path[: len(m.group(1)) - 1] + [m.group(2)]
            sections.append((" > ".join(path), []))
        else:
            sections[-1][1].append(line)
    return [(h, "\n".join(ls).strip()) for h, ls in sections if "\n".join(ls).strip()]


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _split_long(piece: str, size: int) -> list[str]:
    if len(piece) <= size:
        return [piece]
    out, cur = [], ""
    for s in re.split(r"(?<=[.!?])\s+", piece):
        while len(s) > size:
            out.append(s[:size])
            s = s[size:]
        if cur and len(cur) + len(s) + 1 > size:
            out.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    return out + ([cur] if cur else [])


def _pack(units: list[str], size: int, overlap: int) -> list[str]:
    """Greedily pack paragraphs/rows into ~size-char chunks, carrying `overlap` chars forward."""
    out: list[str] = []
    cur = ""
    for p in (p for u in units for p in _split_long(u, size)):
        if cur and len(cur) + len(p) + 2 > size:
            out.append(cur)
            tail = cur[-overlap:] if overlap else ""
            cur = f"{tail}\n\n{p}".strip() if tail else p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    return out + ([cur] if cur else [])
