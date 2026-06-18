"""Route queries about other institutions / out-of-scope topics to web search.

Detects when a query is about a university other than SRKI (e.g. VNSGU) and
composes a grounded, source-cited answer so the assistant does not hallucinate
institutional facts it has no verified data for.
"""
from __future__ import annotations

import re

from backend.app.config import settings
from backend.app.pipeline.web_search import search_with_grounding

# Phrases that mean "this is about SRKI / our own institution".
_INTERNAL_MARKERS = (
    "srki",
    "shree ramkrishna",
    "ramkrishna institute",
)

_INST_PATTERN = re.compile(
    r"\b([a-z][a-z&.\- ]{2,60}?\s(?:university|college|institute|polytechnic))\b", re.I
)

# Acronyms / names that are internal even though they look like institutions.
_INTERNAL_NAMES = ("sarvajanik university", "sarvajanik", "ramkrishna")

_INTENT_QUERY_HINTS = {
    "admission_query": "admission eligibility apply",
    "fee_structure": "fees structure",
    "course_info": "courses programs offered",
    "exam_schedule": "exam timetable schedule",
    "result_query": "result",
    "placement_info": "placement recruiters",
    "contact_info": "contact phone email address",
}


def _mentions_internal(text: str) -> bool:
    return any(m in text for m in _INTERNAL_MARKERS)


def detect_external(text: str) -> dict | None:
    """Return {"institution": str} if the query targets a non-SRKI institution."""
    if not settings.external_search_enabled:
        return None
    lower = text.lower()
    if _mentions_internal(lower):
        return None

    for name in settings.external_institutions_list():
        if name and name in lower:
            return {"institution": name, "matched": "known"}

    match = _INST_PATTERN.search(lower)
    if match:
        candidate = match.group(1).strip()
        if not any(internal in candidate for internal in _INTERNAL_NAMES):
            return {"institution": candidate, "matched": "pattern"}
    return None


def build_query(text: str, intent: str | None, institution: str | None) -> str:
    hint = _INTENT_QUERY_HINTS.get(intent or "", "")
    parts = [text]
    if institution and institution not in text.lower():
        parts.append(institution)
    if hint:
        parts.append(hint)
    return " ".join(parts).strip()


def compose_external_answer(
    text: str, intent: str | None, institution: str | None
) -> dict | None:
    """Search the web and build a grounded answer with cited sources."""
    query = build_query(text, intent, institution)
    payload = search_with_grounding(query, institution)
    results = payload.get("results") or []
    if not results:
        return None

    label = (institution or "this query").strip()
    if institution and institution not in {"this query"}:
        label = institution.upper() if len(institution) <= 6 else institution.title()

    lines = [f"Here is what I found on the web about **{label}** (not SRKI's own data):", ""]
    for i, r in enumerate(results[:4], start=1):
        title = r.get("title") or r.get("url")
        body = (r.get("extract") or r.get("snippet") or "").strip()
        if len(body) > 320:
            body = body[:320].rsplit(" ", 1)[0] + "…"
        lines.append(f"**{i}. {title}**")
        if body:
            lines.append(body)
        lines.append(f"Source: [{r.get('url')}]({r.get('url')})")
        lines.append("")

    lines.append(
        "_Note: This information comes from external public web sources and is **not** "
        "verified by SRKI. Please confirm details on the institution's official website._"
    )
    return {
        "reply": "\n".join(lines).strip(),
        "sources": [r.get("url") for r in results[:4]],
        "grounded": True,
    }
