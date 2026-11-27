"""API contract, authorization at the HTTP boundary, error reporting, and frontend escaping."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def client(rag, monkeypatch):
    import backend.api as api

    monkeypatch.setattr(api, "_rag", rag)
    return TestClient(api.app)


def test_health_reports_stub_and_index(client):
    h = client.get("/api/health").json()
    assert h["llm_is_test_stub"] is True and h["index_chunks"] > 0


def test_users_list_exposes_no_permissions(client):
    users = client.get("/api/users").json()
    assert {"id", "role"} == set(users[0]) and {u["id"] for u in users} >= {"admin", "alice", "bob"}


def test_ask_returns_contract(client):
    r = client.post("/api/ask", json={"user_id": "admin", "question": "What is the return window for kayaks?"})
    assert r.status_code == 200
    body = r.json()
    assert {"answer", "abstained", "citations", "retrieved", "llm_is_test_stub"} <= set(body)


def test_unknown_user_gets_403(client):
    r = client.post("/api/ask", json={"user_id": "mallory", "question": "hi"})
    assert r.status_code == 403


def test_client_cannot_send_its_own_filters(client):
    r = client.post("/api/ask", json={"user_id": "alice", "question": "kayak warranty", "filters": {"folder": "*"}})
    assert r.status_code == 422


def test_authorization_enforced_over_http(client):
    body = client.post("/api/ask", json={"user_id": "alice", "question": "Ridgeline 12 Touring Kayak warranty"}).json()
    assert not any(p["source"].startswith("catalog/") for p in body["retrieved"])


def test_provider_failure_is_reported_not_faked(client, rag, monkeypatch):
    def broken(*_a, **_k):
        raise ConnectionError("provider down")

    monkeypatch.setattr(rag.llm, "complete", broken)
    r = client.post("/api/ask", json={"user_id": "admin", "question": "What is the return window for kayaks?"})
    assert r.status_code == 502 and "provider down" in r.json()["detail"]


def test_frontend_is_served_and_never_uses_innerhtml(client):
    assert client.get("/").status_code == 200 and client.get("/static/app.js").status_code == 200
    js = (ROOT / "frontend" / "app.js").read_text()
    assert "innerHTML" not in js.replace("never innerHTML", "")
    assert "http://" not in (ROOT / "frontend" / "index.html").read_text()  # no external CDN
