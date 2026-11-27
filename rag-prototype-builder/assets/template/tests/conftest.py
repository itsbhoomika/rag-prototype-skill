"""Shared fixtures. Every test runs with no API keys: the offline test stub + keyword search."""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "offline")
    monkeypatch.setenv("EMBED_PROVIDER", "none")
    monkeypatch.setenv("DATA_DIR", str(ROOT / "data" / "sample"))
    monkeypatch.setenv("USERS_FILE", str(ROOT / "data" / "users.json"))
    monkeypatch.setenv("INDEX_DIR", str(tmp_path / "index"))
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    return tmp_path


@pytest.fixture()
def rag(env):
    from backend.pipeline import RAG

    r = RAG()
    stats = r.ingest()
    assert stats["docs"] == 4 and stats["skipped_files"] == []
    return r
