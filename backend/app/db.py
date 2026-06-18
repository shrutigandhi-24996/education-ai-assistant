"""Lightweight SQLite logging of every conversation turn.

Stores one row per user query with the columns from the research design:
user_id, question, intent, multi_intent, context, answer (+ sources, timestamp).
Powers the live database viewer at /admin.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

from backend.app.config import settings

_LOCK = threading.Lock()
_conn: sqlite3.Connection | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT NOT NULL,
    user_id      TEXT,
    question     TEXT,
    intent       TEXT,
    multi_intent TEXT,
    context      TEXT,
    answer       TEXT,
    sources      TEXT
)
"""


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(settings.db_path), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute(_SCHEMA)
        _conn.commit()
    return _conn


def init_db() -> None:
    if settings.conversation_logging_enabled:
        with _LOCK:
            _connect()


def log_conversation(user_id: str, question: str, result: dict[str, Any]) -> None:
    if not settings.conversation_logging_enabled:
        return
    intents = result.get("intents") or ([result["intent"]] if result.get("intent") else [])
    context = {
        "role": result.get("role"),
        "intents": intents,
        "institution": result.get("institution"),
        "is_multi_intent": result.get("is_multi_intent"),
        "answer_source": result.get("source"),
    }
    if isinstance(result.get("context"), dict):
        context["pragmatic"] = result["context"]
    row = (
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
        user_id,
        question,
        result.get("intent"),
        "yes" if result.get("is_multi_intent") else "no",
        json.dumps(context, ensure_ascii=False),
        result.get("reply"),
        json.dumps(result.get("sources") or [], ensure_ascii=False),
    )
    try:
        with _LOCK:
            conn = _connect()
            conn.execute(
                "INSERT INTO conversations "
                "(created_at, user_id, question, intent, multi_intent, context, answer, sources) "
                "VALUES (?,?,?,?,?,?,?,?)",
                row,
            )
            conn.commit()
    except Exception:
        # Logging must never break the chat response.
        pass


def recent(limit: int = 100) -> list[dict[str, Any]]:
    if not settings.conversation_logging_enabled:
        return []
    try:
        with _LOCK:
            conn = _connect()
            cur = conn.execute(
                "SELECT id, created_at, user_id, question, intent, multi_intent, "
                "context, answer, sources FROM conversations ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = [dict(r) for r in cur.fetchall()]
    except Exception:
        return []
    for r in rows:
        for col in ("context", "sources"):
            try:
                r[col] = json.loads(r[col]) if r.get(col) else None
            except Exception:
                pass
    return rows


def count() -> int:
    try:
        with _LOCK:
            conn = _connect()
            return int(conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0])
    except Exception:
        return 0
