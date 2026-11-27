"""HTTP API + serves the frontend.   Run:  uvicorn backend.api:app --reload

Endpoints
  GET  /api/health   -> provider names, index size, whether the LLM is the test stub
  GET  /api/users    -> [{id, role}] for the demo user picker (no permissions exposed)
  POST /api/ask      -> {user_id, question} -> AskResponse

Authorization: the request carries only user_id. Allowed folders are looked up on the
server (backend/auth.py). There is deliberately no way to send filters from the client.
Identity is SIMULATED: there is no login, so the caller chooses user_id. Production takes it
from a verified session (SSO/JWT) and keeps everything else the same.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .auth import UnknownUser
from .pipeline import RAG

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
log = logging.getLogger("rag.api")


# ---------------------------------------------------------------- API contract
class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")  # a client trying to send its own "filters" gets a 422

    user_id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=1, max_length=2000)


class Passage(BaseModel):
    label: str
    chunk_id: str
    doc_id: str
    position: int
    source: str
    section: str
    page: int | None
    text: str
    score: float
    bm25: float | None
    vector_sim: float | None


class FlaggedPassage(BaseModel):
    label: str
    source: str
    quote: str                     # the sentence that looked like an instruction
    cited: bool                    # whether the answer still cites this passage


class AskResponse(BaseModel):
    question: str
    user_id: str
    answer: str
    abstained: bool
    reason: str
    warnings: list[str]
    numbers_checked: int           # numbers in the answer, each found in a cited passage by the guard
    searched_folders: list[str]    # folders this user's search covered
    unsearched_folders: list[str]  # indexed folders this user can't search (empty if SHOW_UNSEARCHED_FOLDERS=0)
    ignored_instructions: list[FlaggedPassage]  # retrieved passages that talk to the model
    citations: list[Passage]
    retrieved: list[Passage]       # only passages this user is allowed to see
    llm: str
    llm_is_test_stub: bool
    embedder: str
    timings: dict[str, float]


class UserOut(BaseModel):
    id: str
    role: str


# ---------------------------------------------------------------- app
app = FastAPI(title="RAG prototype")
_rag: RAG | None = None


def rag() -> RAG:
    global _rag
    if _rag is None:
        _rag = RAG()
    return _rag


@app.get("/api/health")
def health() -> dict:
    r = rag()
    try:
        chunks = len(r.index.chunks)
    except FileNotFoundError:
        chunks = 0
    return {"llm": r.llm.name, "llm_is_test_stub": r.llm.provider == "offline",
            "embedder": r.embedder.name, "index_chunks": chunks}


@app.get("/api/users", response_model=list[UserOut])
def users() -> list[UserOut]:
    return [UserOut(id=u.id, role=u.role) for u in rag().users.values()]


@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest) -> dict:
    try:
        return rag().ask(req.question, req.user_id)
    except UnknownUser as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # provider/network failure: report it, never return a made-up answer
        # The browser gets the error type; the full message (which can name endpoints, deployments
        # or account details) goes to the server log only.
        log.exception("ask failed for user %s", req.user_id)
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: the model or embedding provider "
                                                    "failed. Full details are in the server log.") from e


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
