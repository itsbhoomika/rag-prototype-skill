"""Authorization: the server decides what each user may see.

The client sends only a user id. The allowed folders come from data/users.json on the
server, are turned into retrieval filters here, and are applied before scoring.
The client can never send its own filters.

Prototype limit: the user id is taken on trust from the request (no login). In
production it would come from a verified session or token (e.g. SSO / JWT).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class UnknownUser(PermissionError):
    pass


@dataclass(frozen=True)
class User:
    id: str
    role: str
    allowed_folders: tuple[str, ...]


def load_users(path: Path) -> dict[str, User]:
    if not path.exists():
        raise FileNotFoundError(f"Users file not found: {path}")
    raw = json.loads(path.read_text())
    return {
        uid: User(uid, u.get("role", ""), tuple(u.get("allowed_folders", [])))
        for uid, u in raw.get("users", {}).items()
    }


def filters_for(users: dict[str, User], user_id: str) -> dict:
    """Unknown user -> error. Known user with no folders -> sees nothing (deny by default)."""
    user = users.get(user_id)
    if user is None:
        raise UnknownUser(f"unknown user '{user_id}'")
    return {"folder": list(user.allowed_folders) or ["__none__"]}
