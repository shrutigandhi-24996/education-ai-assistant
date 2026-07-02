"""Navigate official college websites (menus/sub-pages) to find syllabus PDFs."""

from __future__ import annotations

import re
from collections import deque
from typing import Any
from urllib.parse import urlparse

from backend.app.config import settings
from backend.app.pipeline.page_assets import _asset_type, _clean_text, _HREF_RE
from backend.app.pipeline.web_search import _http_get, search_web

_SYLLABUS_WORDS = (
    "syllabus", "curriculum", "scheme", "regulation", "credit", "nep",
    "academics", "academic", "programme", "program",
)
_NAV_WORDS = (
    "academics", "academic", "department", "programme", "program", "course",
    "su syllabus", "syllabus", "upload", "courses-offered", "su-syllabus",
)
_PROGRAM_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bbscit\b", re.I), "it"),
    (re.compile(r"\bb\.?\s*sc\.?\s*(?:it|information\s+technology)\b", re.I), "it"),
    (re.compile(r"\bbsccs\b|\bb\.?\s*sc\.?\s*(?:cs|computer\s+science)\b", re.I), "cs"),
    (re.compile(r"\bb\.?\s*sc\.?\s*mb\b", re.I), "mb"),
    (re.compile(r"\bb\.?\s*sc\.?\s*bt\b", re.I), "bt"),
    (re.compile(r"\bb\.?\s*sc\b", re.I), "bsc"),
    (re.compile(r"\bm\.?\s*sc\b", re.I), "msc"),
    (re.compile(r"\bmba\b", re.I), "mba"),
    (re.compile(r"\bbca\b", re.I), "bca"),
    (re.compile(r"\bb\.?\s*tech\b", re.I), "btech"),
]
_SEM_RE = re.compile(r"\bsem(?:ester)?[\s\-]*(\d+)\b", re.I)
_YEAR_RE = re.compile(r"\b(20\d{2})[\s\-/]+(?:20)?(\d{2})\b")


def parse_syllabus_intent(query: str) -> dict[str, Any]:
    low = query.lower()
    is_syllabus = "syllabus" in low or (
        bool(_SEM_RE.search(query))
        and any(w in low for w in ("course", "bsc", "b.sc", "m.sc", "program", "subject", "sem"))
    )
    programs: list[str] = []
    for pat, slug in _PROGRAM_PATTERNS:
        if pat.search(query):
            programs.append(slug)
    sem_m = _SEM_RE.search(query)
    semester = int(sem_m.group(1)) if sem_m else None
    year_m = _YEAR_RE.search(query)
    year = f"{year_m.group(1)}-{year_m.group(2)}" if year_m else None
    return {
        "is_syllabus": is_syllabus,
        "programs": programs,
        "semester": semester,
        "year": year,
    }


def is_syllabus_query(query: str) -> bool:
    return bool(parse_syllabus_intent(query).get("is_syllabus"))


def _same_site(url: str, root_host: str) -> bool:
    try:
        return urlparse(url).netloc.lower().replace("www.", "") == root_host
    except Exception:
        return False


def _score_nav_link(url: str, label: str, intent: dict[str, Any], depth: int) -> int:
    blob = f"{url} {label}".lower().replace(" ", "")
    score = max(0, 10 - depth * 2)
    if _asset_type(url) == "pdf":
        score += 12
    for w in _SYLLABUS_WORDS:
        if w.replace(" ", "") in blob or w in blob:
            score += 4
    for w in _NAV_WORDS:
        if w.replace(" ", "") in blob or w in blob:
            score += 2
    for prog in intent.get("programs") or []:
        if prog in blob or prog.replace("bsc", "b.sc") in blob:
            score += 6
    sem = intent.get("semester")
    if sem:
        sem_hits = (f"sem{sem}", f"sem-{sem}", f"semester{sem}", f"semester-{sem}")
        if any(h in blob for h in sem_hits):
            score += 10
    year = intent.get("year")
    if year and year.replace("-", "")[:6] in blob.replace("-", ""):
        score += 4
    if "upload" in blob and _asset_type(url) == "pdf":
        score += 5
    if "nep" in blob:
        score += 3
    return score


def _extract_links(html: str, page_url: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for href_raw, inner in _HREF_RE.findall(html):
        href = href_raw.strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        from urllib.parse import urljoin

        full = urljoin(page_url, href)
        if not full.startswith("http"):
            continue
        label = _clean_text(inner) or full.rsplit("/", 1)[-1]
        items.append((full, label))
    return items


def crawl_for_syllabus_pdfs(
    seed_urls: list[str],
    query: str,
    max_pages: int | None = None,
    max_depth: int | None = None,
) -> list[dict[str, Any]]:
    """Walk official site menus (BFS) and search for matching syllabus PDFs."""
    intent = parse_syllabus_intent(query)
    if not intent["is_syllabus"]:
        return []

    max_pages = max_pages or (6 if settings.edu_fast_mode else settings.edu_site_nav_max_pages)
    max_depth = max_depth or (2 if settings.edu_fast_mode else settings.edu_site_nav_max_depth)

    pdfs: list[dict[str, Any]] = []
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque()

    for url in seed_urls:
        if url and url not in visited:
            queue.append((url, 0))

    pages_scanned = 0
    while queue and pages_scanned < max_pages:
        url, depth = queue.popleft()
        if url in visited or depth > max_depth:
            continue
        visited.add(url)

        if _asset_type(url) == "pdf":
            label = url.rsplit("/", 1)[-1]
            score = _score_nav_link(url, label, intent, depth)
            if score >= 12:
                pdfs.append(
                    {
                        "type": "pdf",
                        "url": url,
                        "title": label,
                        "score": score,
                        "source": "site_nav",
                    }
                )
            continue

        try:
            html = _http_get(url, timeout=8 if settings.edu_fast_mode else 12)
        except Exception:
            continue
        if not html or len(html) < 100:
            continue
        pages_scanned += 1

        root_host = urlparse(url).netloc.lower().replace("www.", "")
        for link, label in _extract_links(html, url):
            score = _score_nav_link(link, label, intent, depth + 1)
            if _asset_type(link) == "pdf" and score >= 12:
                pdfs.append(
                    {
                        "type": "pdf",
                        "url": link,
                        "title": label[:200] or link.rsplit("/", 1)[-1],
                        "page": url,
                        "score": score,
                        "source": "site_nav",
                    }
                )
            elif depth + 1 <= max_depth and score >= 4 and _same_site(link, root_host):
                if link not in visited:
                    queue.append((link, depth + 1))

    if len(pdfs) < 2 and seed_urls:
        host = urlparse(seed_urls[0]).netloc.replace("www.", "")
        prog = " ".join(intent.get("programs") or ["syllabus"])
        sem = f"sem {intent['semester']}" if intent.get("semester") else ""
        year = intent.get("year") or "2024-25"
        ddg_q = f"site:{host} {prog} {sem} {year} syllabus pdf".strip()
        for r in search_web(ddg_q, max_results=5):
            u = r.get("url") or ""
            if ".pdf" not in u.lower():
                continue
            label = r.get("title") or u.rsplit("/", 1)[-1]
            score = _score_nav_link(u, label, intent, 0) + 6
            pdfs.append(
                {
                    "type": "pdf",
                    "url": u,
                    "title": label[:200],
                    "score": score,
                    "source": "search",
                }
            )

    pdfs.sort(key=lambda x: x.get("score", 0), reverse=True)
    seen_urls: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in pdfs:
        u = item.get("url", "")
        if not u or u in seen_urls:
            continue
        seen_urls.add(u)
        out.append(item)
    return out[:6]
