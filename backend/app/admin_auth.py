"""Simple admin session tokens (in-memory). Set ADMIN_PASSWORD in .env / Render."""

from __future__ import annotations

import secrets
import threading
import time

from fastapi import Header, HTTPException

from backend.app.config import settings

_tokens: dict[str, float] = {}
_lock = threading.Lock()


def admin_configured() -> bool:
    return bool(settings.admin_password.strip())


def _prune_locked(now: float | None = None) -> None:
    now = now or time.time()
    for token, exp in list(_tokens.items()):
        if exp <= now:
            del _tokens[token]


def login(username: str, password: str) -> str | None:
    if not admin_configured():
        return None
    if username != settings.admin_username or password != settings.admin_password:
        return None
    token = secrets.token_urlsafe(32)
    ttl = max(1, settings.admin_token_ttl_hours) * 3600
    with _lock:
        _prune_locked()
        _tokens[token] = time.time() + ttl
    return token


def verify_token(token: str | None) -> bool:
    if not token or not admin_configured():
        return False
    with _lock:
        _prune_locked()
        exp = _tokens.get(token)
        return exp is not None and exp > time.time()


def logout(token: str) -> None:
    with _lock:
        _tokens.pop(token, None)


async def require_admin(authorization: str | None = Header(None)) -> str:
    if not admin_configured():
        raise HTTPException(
            status_code=503,
            detail="Admin access is not configured. Set ADMIN_PASSWORD on the server.",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Admin login required.")
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="Invalid or expired admin session.")
    return token
