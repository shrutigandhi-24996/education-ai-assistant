"""Search cached (and optionally live) web content for answers."""
from __future__ import annotations

import re
from typing import Any

from backend.app.config import settings
from backend.app.pipeline import web_scraper
from backend.app.pipeline.web_text import clean_snippet, snippet_is_useful

INTENT_KEYWORDS: dict[str, list[str]] = {
    "admission_query": ["admission", "apply", "eligibility", "form", "academic year", "merit"],
    "fee_structure": ["fee", "fees", "tuition", "payment", "scholarship", "structure"],
    "contact_info": ["contact", "phone", "email", "address", "whatsapp", "call", "info@srki"],
    "placement_info": ["placement", "recruiter", "company", "career"],
    "event_info": ["event", "fest", "notice", "workshop", "seminar"],
    "exam_schedule": ["exam", "timetable", "schedule", "practical", "internal", "examination"],
    "course_info": ["course", "program", "syllabus", "semester", "curriculum", "degree", "offered"],
    "infrastructure_info": ["lab", "library", "hostel", "campus", "facility", "laboratory"],
    "faculty_info": ["faculty", "professor", "teacher", "department"],
    "result_query": ["result", "marks", "grade"],
    "general_greeting": ["about", "welcome", "institute", "college", "vision", "mission"],
}

INTENT_URL_HINTS: dict[str, list[str]] = {
    "admission_query": ["admission-corner", "admission"],
    "fee_structure": ["fees-structure", "fees"],
    "contact_info": ["contact"],
    "placement_info": ["placement"],
    "exam_schedule": ["examination", "timetable", "previous-question"],
    "course_info": ["courses-offered", "su-syllabus", "department"],
    "infrastructure_info": ["library", "laboratory", "hostel", "canteen", "playground"],
    "event_info": ["event", "notice", "e-magazine"],
}

INTENT_REQUIRED_IN_CHUNK: dict[str, list[str]] = {
    "placement_info": ["placement", "recruiter", "career", "employability"],
    "fee_structure": ["fee", "fees", "tuition", "structure"],
    "contact_info": ["contact", "email", "phone", "722801849", "info@srki"],
    "exam_schedule": ["exam", "timetable", "schedule", "examination", "paper"],
    "infrastructure_info": ["library", "lab", "hostel", "campus", "facility", "laboratory"],
}


def _chunk_matches_intent(intent: str | None, cleaned: str) -> bool:
    if not intent or intent not in INTENT_REQUIRED_IN_CHUNK:
        return True
    lower = cleaned.lower()
    return any(kw in lower for kw in INTENT_REQUIRED_IN_CHUNK[intent])


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def _url_boost(intent: str | None, url: str) -> float:
    if not intent or not url:
        return 0.0
    lower = url.lower()
    boost = 0.0
    for hint in INTENT_URL_HINTS.get(intent, []):
        if hint in lower:
            boost += 8.0
    return boost


def _score_chunk(query: str, intent: str | None, chunk: str, title: str, url: str) -> float:
    cleaned = clean_snippet(chunk, max_len=5000)
    if not snippet_is_useful(cleaned, min_unique_words=8):
        return -1.0
    if not _chunk_matches_intent(intent, cleaned):
        return -1.0

    q = _tokens(query)
    c = _tokens(cleaned) | _tokens(title)
    if not q:
        return 0.0
    overlap = len(q & c) / max(len(q), 1)
    score = overlap * 10.0
    if intent:
        for kw in INTENT_KEYWORDS.get(intent, []):
            if kw in cleaned.lower() or kw in url.lower():
                score += 2.0
    score += _url_boost(intent, url)
    if "404" in title.lower() or "404-error" in cleaned.lower()[:120]:
        score -= 20.0
    return score


class WebKnowledge:
    def __init__(self) -> None:
        self._pages: list[dict] = []
        self._loaded = False

    def ensure_cache(self, force: bool = False) -> None:
        if not settings.web_scrape_enabled:
            return
        if force or not web_scraper.cache_is_fresh():
            try:
                web_scraper.refresh_cache_if_needed(force=force)
            except Exception:
                pass
        self._pages = web_scraper.load_cache()
        self._loaded = True

    @property
    def page_count(self) -> int:
        return len([p for p in self._pages if p.get("chunks")])

    def _page_excerpt(self, url_hint: str, query: str, max_len: int = 900) -> dict | None:
        q = _tokens(query)
        best: dict | None = None
        best_score = -1.0
        for page in self._pages:
            url = (page.get("url") or "").lower()
            if url_hint not in url or page.get("error"):
                continue
            text = clean_snippet(page.get("text") or "", max_len=10000)
            if not text:
                continue
            overlap = len(q & _tokens(text)) / max(len(q), 1)
            if overlap > best_score:
                best_score = overlap
                best = {
                    "chunk": text[:max_len],
                    "url": page.get("url"),
                    "title": page.get("title", "SRKI"),
                    "score": overlap * 10 + 5,
                }
        return best

    def search(self, query: str, intent: str | None = None, top_k: int = 3) -> list[dict]:
        if not settings.web_scrape_enabled:
            return []
        if not self._loaded:
            self.ensure_cache()
        hits: list[dict] = []
        for page in self._pages:
            if page.get("error") or not page.get("chunks"):
                continue
            url = page.get("url", "")
            title = page.get("title", "")
            for chunk in page["chunks"]:
                score = _score_chunk(query, intent, chunk, title, url)
                if score < 2.0:
                    continue
                cleaned = clean_snippet(chunk)
                hits.append(
                    {
                        "score": score,
                        "chunk": cleaned,
                        "url": url,
                        "title": title,
                    }
                )
        hits.sort(key=lambda x: x["score"], reverse=True)

        if intent and intent in INTENT_URL_HINTS and (not hits or hits[0]["score"] < 8):
            for hint in INTENT_URL_HINTS[intent]:
                excerpt = self._page_excerpt(hint, query)
                if excerpt and _chunk_matches_intent(intent, excerpt["chunk"]):
                    hits.insert(0, excerpt)
                    break

        return hits[:top_k]

    def compose_answer(
        self, query: str, intent: str | None = None, context: dict[str, Any] | None = None
    ) -> str | None:
        hits = self.search(query, intent=intent, top_k=3)
        if not hits:
            if settings.web_live_on_query:
                web_scraper.refresh_cache_if_needed(force=True)
                self._pages = web_scraper.load_cache()
                hits = self.search(query, intent=intent, top_k=3)
            if not hits:
                return None

        lines = ["## Latest information from official SRKI website", ""]
        if context and context.get("Course"):
            lines.append(f"_Topic: {', '.join(context['Course'])}_")
            lines.append("")

        used_urls: set[str] = set()
        shown = 0
        for hit in hits:
            url = hit.get("url") or ""
            if url in used_urls:
                continue
            used_urls.add(url)
            shown += 1
            title = hit.get("title", "SRKI")
            title = re.sub(
                r"\s*-\s*Shree Ramkrishna Institute.*$",
                "",
                title,
                flags=re.I,
            ).strip() or "SRKI"
            lines.append(f"### {title}")
            lines.append(hit["chunk"])
            lines.append(f"[Read more]({url})")
            lines.append("")
            if shown >= 2:
                break

        if shown == 0:
            return None

        lines.append(
            "_Source: official srki.ac.in pages (cached). For semester syllabus, ask with program and sem number._"
        )
        return "\n".join(lines).strip()

    def enrich(self, base_answer: str, query: str, intent: str | None) -> str:
        """Append web snippet only when highly relevant (avoid noise on syllabus answers)."""
        if not settings.web_scrape_enabled:
            return base_answer
        if intent == "course_info" and re.search(r"sem(?:ester)?[- ]?\d", query.lower()):
            return base_answer
        hits = self.search(query, intent=intent, top_k=1)
        if not hits or hits[0]["score"] < 6.0:
            return base_answer
        hit = hits[0]
        url = (hit.get("url") or "").lower()
        if intent and intent in INTENT_URL_HINTS:
            if not any(h in url for h in INTENT_URL_HINTS[intent]):
                return base_answer
        title = re.sub(
            r"\s*-\s*Shree Ramkrishna Institute.*$",
            "",
            hit.get("title", "SRKI"),
            flags=re.I,
        ).strip()
        return (
            f"{base_answer}\n\n---\n\n"
            f"**Updated from website** ({title}):\n"
            f"{hit['chunk']}\n\n"
            f"[Source]({hit.get('url')})"
        )
