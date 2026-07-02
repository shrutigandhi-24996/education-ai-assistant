"""Resolve unknown college/university/school short names via web search."""

from __future__ import annotations

import re
from typing import Any

from backend.app.pipeline.institution_disambiguation import (
    INSTITUTION_ALIASES,
    INSTITUTION_HOMOGRAPHS,
    detect_institution,
    expand_institution_aliases,
)
from backend.app.pipeline.web_search import search_web

_SKIP = {
    "the", "a", "an", "my", "for", "and", "or", "of", "in", "at", "to", "from",
    "with", "about", "what", "when", "where", "how", "give", "show", "tell",
    "please", "want", "need", "sem", "semester", "syllabus", "course", "pdf",
    "official", "website", "link", "details", "information",
}
_FACTUAL = (
    "admission", "fee", "fees", "syllabus", "course", "sem", "exam", "department",
    "faculty", "placement", "scholarship", "eligibility", "apply",
)
_INSTITUTION_WORD = re.compile(
    r"\b(college|university|school|institute|institution|polytechnic|academy|campus)\b",
    re.I,
)
_TOKEN = re.compile(r"\b([A-Za-z]{2,10})\b")
_NAME_CLEAN = re.compile(r"\s*[\|\-–—:].*$")


def find_unknown_institution_tokens(query: str, resolved: dict[str, str]) -> list[str]:
    """Tokens that may be unknown institution short names (not in local alias tables)."""
    if detect_institution(query, resolved):
        return []
    expanded = expand_institution_aliases(query, resolved)
    lower = expanded.lower()
    found: list[str] = []
    for match in _TOKEN.finditer(expanded):
        tok = match.group(1).lower()
        if tok in _SKIP or tok in resolved or tok in INSTITUTION_ALIASES or tok in INSTITUTION_HOMOGRAPHS:
            continue
        has_inst_word = bool(_INSTITUTION_WORD.search(lower))
        has_factual = any(w in lower for w in _FACTUAL)
        if not has_inst_word and not has_factual:
            continue
        if re.search(rf"\b{re.escape(tok)}\b", lower):
            found.append(tok)
    return list(dict.fromkeys(found))[:2]


def _looks_like_institution(name: str, snippet: str = "") -> bool:
    blob = f"{name} {snippet}".lower()
    return bool(_INSTITUTION_WORD.search(blob) or "university" in blob or "college" in blob)


def search_institution_by_short_name(token: str, context: str = "") -> list[dict[str, str]]:
    """Search the web (DuckDuckGo) to identify what a short name refers to."""
    queries = [
        f"{token} college university official name",
        f"{token} {context} college university".strip(),
    ]
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    for q in queries:
        if not q.strip():
            continue
        for r in search_web(q, max_results=5):
            title = _NAME_CLEAN.sub("", (r.get("title") or "")).strip()
            snippet = (r.get("snippet") or "").strip()
            url = r.get("url") or ""
            name = title
            if not _looks_like_institution(name, snippet):
                continue
            key = name.lower()
            if key in seen or len(name) < 6:
                continue
            seen.add(key)
            candidates.append(
                {
                    "resolution": name,
                    "label": f"{token.upper()} — {name}",
                    "url": url,
                }
            )
        if len(candidates) >= 3:
            break
    return candidates[:5]


def format_web_institution_clarification(token: str, options: list[dict[str, str]]) -> str:
    lines = [
        f"I searched the web for **'{token.upper()}'** and found more than one institution. "
        "Which one do you mean?"
    ]
    for i, opt in enumerate(options, 1):
        lines.append(f"{i}. {opt['label']}")
    lines.append("Reply with the **number**, the **full name**, or tap an option below.")
    return "\n".join(lines)


def build_web_clarification_options(token: str, options: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, opt in enumerate(options, 1):
        out.append(
            {
                "kind": "web_institution",
                "term": token,
                "label": opt["label"],
                "value": str(i),
                "resolution": opt["resolution"],
            }
        )
    return out
