"""Lightweight SQLite logging of every conversation turn.

Matches the research / UI design:
  user_id, session_id, question, intent, multi_intent (JSON list), context, answer

Also records conversation scenario (single/multi intent, multi-turn) and turn index
within a session so all five infographic cases can be analysed from the DB.
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
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL,
    user_id       TEXT NOT NULL,
    session_id    TEXT NOT NULL,
    turn_index    INTEGER NOT NULL DEFAULT 1,
    scenario      TEXT,
    question      TEXT,
    intent        TEXT,
    multi_intent  TEXT,
    context       TEXT,
    answer        TEXT,
    sources       TEXT
)
"""


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(settings.db_path), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute(_SCHEMA)
        _migrate(_conn)
        _conn.commit()
    return _conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after the first schema without losing old rows."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(conversations)")}
    additions = {
        "session_id": "TEXT",
        "turn_index": "INTEGER DEFAULT 1",
        "scenario": "TEXT",
    }
    for col, typedef in additions.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE conversations ADD COLUMN {col} {typedef}")
    # Back-fill session_id from legacy rows that only stored session in user_id.
    if "session_id" in existing or "session_id" in additions:
        conn.execute(
            "UPDATE conversations SET session_id = user_id "
            "WHERE session_id IS NULL OR session_id = ''"
        )


def init_db() -> None:
    if settings.conversation_logging_enabled:
        with _LOCK:
            _connect()


def _turn_index(conn: sqlite3.Connection, session_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM conversations WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    return int(row[0]) + 1 if row else 1


def _scenario(turn_index: int, intents: list[str]) -> str:
    """Map a turn to the conversation-scenario labels from the research diagrams."""
    multi = len(intents) > 1
    if turn_index <= 1 and not multi:
        return "single_user_single_question_single_intent"
    if turn_index <= 1 and multi:
        return "single_user_single_question_multiple_intent"
    if turn_index > 1 and not multi:
        return "single_user_multiple_questions_single_intent"
    return "single_user_multiple_questions_multiple_intent"


def _build_context(result: dict[str, Any], intents: list[str]) -> dict[str, Any]:
    """Pragmatic context JSON (Course, Institution, Role, …) for the DB column."""
    ctx: dict[str, Any] = {}
    if isinstance(result.get("context"), dict):
        ctx.update(result["context"])
    role = result.get("role")
    if role:
        ctx.setdefault("Role", [])
        label = str(role).title()
        if label not in ctx["Role"]:
            ctx["Role"].append(label)
    institution = result.get("institution")
    if institution:
        ctx.setdefault("Institution", [])
        if institution not in ctx["Institution"]:
            ctx["Institution"].append(institution)
    if intents:
        ctx["Intents"] = intents
    if result.get("is_multi_intent"):
        ctx["MultiIntent"] = True
    if result.get("source"):
        ctx["AnswerSource"] = result["source"]
    return ctx


def log_conversation(
    user_id: str,
    session_id: str,
    question: str,
    result: dict[str, Any],
) -> None:
    if not settings.conversation_logging_enabled:
        return

    intents: list[str] = list(result.get("intents") or [])
    if not intents and result.get("intent"):
        intents = [str(result["intent"])]
    primary_intent = intents[0] if intents else result.get("intent")
    is_multi = bool(result.get("is_multi_intent")) or len(intents) > 1
    context = _build_context(result, intents)

    try:
        with _LOCK:
            conn = _connect()
            turn = _turn_index(conn, session_id)
            scenario = _scenario(turn, intents)
            row = (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                user_id or "anonymous",
                session_id or "default",
                turn,
                scenario,
                question,
                primary_intent,
                json.dumps(intents, ensure_ascii=False) if intents else "[]",
                json.dumps(context, ensure_ascii=False),
                result.get("reply"),
                json.dumps(result.get("sources") or [], ensure_ascii=False),
            )
            conn.execute(
                "INSERT INTO conversations "
                "(created_at, user_id, session_id, turn_index, scenario, question, "
                "intent, multi_intent, context, answer, sources) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
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
                "SELECT id, created_at, user_id, session_id, turn_index, scenario, "
                "question, intent, multi_intent, context, answer, sources "
                "FROM conversations ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = [dict(r) for r in cur.fetchall()]
    except Exception:
        return []
    for r in rows:
        for col in ("multi_intent", "context", "sources"):
            try:
                r[col] = json.loads(r[col]) if r.get(col) else ([] if col != "context" else {})
            except Exception:
                if col == "multi_intent":
                    r[col] = []
                elif col == "context":
                    r[col] = {}
                else:
                    r[col] = []
    return rows


def count() -> int:
    try:
        with _LOCK:
            conn = _connect()
            return int(conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0])
    except Exception:
        return 0


def fetch_all() -> list[dict[str, Any]]:
    """All rows for export (oldest first)."""
    if not settings.conversation_logging_enabled:
        return []
    try:
        with _LOCK:
            conn = _connect()
            cur = conn.execute(
                "SELECT id, created_at, user_id, session_id, turn_index, scenario, "
                "question, intent, multi_intent, context, answer, sources "
                "FROM conversations ORDER BY id ASC"
            )
            rows = [dict(r) for r in cur.fetchall()]
    except Exception:
        return []
    for r in rows:
        for col in ("multi_intent", "context", "sources"):
            try:
                val = r.get(col)
                if col == "context":
                    r[col] = json.loads(val) if val else {}
                elif col in ("multi_intent", "sources"):
                    r[col] = json.loads(val) if val else []
            except Exception:
                r[col] = {} if col == "context" else []
    return rows


def clear_all() -> int:
    """Delete every logged conversation. Returns rows removed."""
    global _conn
    try:
        with _LOCK:
            conn = _connect()
            n = int(conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0])
            conn.execute("DELETE FROM conversations")
            conn.commit()
            return n
    except Exception:
        return 0


def _row_for_export(r: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(r.get("id", "")),
        "created_at": str(r.get("created_at", "")),
        "user_id": str(r.get("user_id", "")),
        "session_id": str(r.get("session_id", "")),
        "turn_index": str(r.get("turn_index", "")),
        "scenario": str(r.get("scenario", "")),
        "question": str(r.get("question", "")),
        "intent": str(r.get("intent", "")),
        "multi_intent": json.dumps(r.get("multi_intent") or [], ensure_ascii=False),
        "context": json.dumps(r.get("context") or {}, ensure_ascii=False),
        "answer": str(r.get("answer") or ""),
        "sources": json.dumps(r.get("sources") or [], ensure_ascii=False),
    }


EXPORT_COLUMNS = [
    "id", "created_at", "user_id", "session_id", "turn_index", "scenario",
    "question", "intent", "multi_intent", "context", "answer", "sources",
]


def export_csv_bytes() -> bytes:
    import csv
    import io

    buf = io.StringIO()
    rows = fetch_all()
    writer = csv.DictWriter(buf, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(_row_for_export(r))
    return buf.getvalue().encode("utf-8-sig")


def export_xlsx_bytes() -> bytes:
    import io

    try:
        from openpyxl import Workbook
    except ImportError:
        return export_csv_bytes()

    wb = Workbook()
    ws = wb.active
    ws.title = "Conversations"
    ws.append(EXPORT_COLUMNS)
    for r in fetch_all():
        flat = _row_for_export(r)
        ws.append([flat[c] for c in EXPORT_COLUMNS])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_pdf_bytes() -> bytes:
    import io

    try:
        from fpdf import FPDF
    except ImportError:
        return b"PDF export requires fpdf2 package."

    rows = fetch_all()
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("Helvetica", size=7)
    cols = ["id", "created_at", "user_id", "question", "intent", "multi_intent"]
    pdf.cell(0, 8, "Innovative Educational Chatbot - Conversation Export", ln=True)
    pdf.ln(2)
    for r in rows:
        flat = _row_for_export(r)
        line = " | ".join(f"{c}: {flat[c][:80]}" for c in cols)
        pdf.multi_cell(0, 4, line)
        pdf.ln(1)
    out = pdf.output()
    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    return str(out).encode("latin-1", errors="replace")
