"""All settings, read from environment variables (and .env if present)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # optional: keeps keys and settings in one git-ignored file
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else default


@dataclass
class Settings:
    llm_provider: str        # anthropic | openai | azure | gemini | ollama | offline (explicit test stub)
    llm_model: str           # blank = provider default
    embed_provider: str      # none (keyword search only) | openai | azure | gemini | ollama | local
    embed_model: str
    chunk_size: int          # characters
    chunk_overlap: int
    top_k: int               # passages sent to the LLM
    candidates: int          # per-retriever candidates before fusion
    min_vector_sim: float    # relevance gate for vector search
    claude_effort: str
    claude_fallbacks: bool
    data_dir: Path
    users_file: Path
    index_dir: Path
    log_dir: Path

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            llm_provider=_env("LLM_PROVIDER", "anthropic").lower(),
            llm_model=_env("LLM_MODEL", ""),
            embed_provider=_env("EMBED_PROVIDER", "none").lower(),
            embed_model=_env("EMBED_MODEL", ""),
            chunk_size=int(_env("CHUNK_SIZE", "1200")),
            chunk_overlap=int(_env("CHUNK_OVERLAP", "150")),
            top_k=int(_env("TOP_K", "6")),
            candidates=int(_env("CANDIDATES", "30")),
            min_vector_sim=float(_env("MIN_VECTOR_SIM", "0.25")),
            claude_effort=_env("CLAUDE_EFFORT", "low"),
            claude_fallbacks=_env("CLAUDE_FALLBACKS", "1") == "1",
            data_dir=Path(_env("DATA_DIR", "data/sample")),
            users_file=Path(_env("USERS_FILE", "data/users.json")),
            index_dir=Path(_env("INDEX_DIR", ".index")),
            log_dir=Path(_env("LOG_DIR", "logs")),
        )
