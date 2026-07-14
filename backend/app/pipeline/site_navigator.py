"""Navigate official college websites (menus/sub-menus) to find PDFs and pages."""

from __future__ import annotations

import heapq
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from backend.app.config import settings
from backend.app.pipeline.institution_catalog import get_crawl_limits
from backend.app.pipeline.official_links import get_institution_domains, is_junk_pdf, url_belongs_to_institution
from backend.app.pipeline.page_assets import _asset_type, _clean_text, _HREF_RE, _extract_image_assets
from backend.app.pipeline.web_search import _http_get, search_web

_SYLLABUS_WORDS = (
    "syllabus", "curriculum", "scheme", "regulation", "credit", "nep",
    "academics", "academic", "programme", "program",
)
_NAV_WORDS = (
    "academics", "academic", "department", "programme", "program", "course",
    "su syllabus", "syllabus", "upload", "courses-offered", "su-syllabus",
    "menu", "study", "learning",
)
_TOPIC_WORDS = {
    "syllabus": _SYLLABUS_WORDS,
    "admission": ("admission", "admissions", "apply", "eligibility", "prospectus"),
    "fee": ("fee", "fees", "tuition", "charges"),
    "exam": ("exam", "result", "timetable", "notification"),
    "contact": ("contact", "address", "phone", "email", "location", "map"),
}
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
_PROGRAM_URL_HINTS: dict[str, tuple[str, ...]] = {
    "it": ("bsc_it", "bscit", "informationtechnology", "information-technology", "_it_", " it "),
    "cs": ("bsc_cs", "bsccs", "computerscience", "computer-science", "_cs_", " cs "),
    "mb": ("microbiology", "_mb_", " mb "),
    "bt": ("biotechnology", "_bt_", " bt "),
    "bsc": ("bsc", "b.sc", "bachelor"),
}
_SEM_RE = re.compile(r"\bsem(?:ester)?[\s\-]*(\d+)\b", re.I)
_YEAR_RE = re.compile(r"\b(20\d{2})[\s\-/]+(?:20)?(\d{2})\b")
_MENU_BLOCK = re.compile(
    r"<(?:nav|header|aside|div|ul|section)[^>]*(?:class|id)=[\"'][^\"']*(?:menu|nav|sidebar|academic|sub-menu|submenu|dropdown)[^\"']*[\"'][^>]*>(.*?)</(?:nav|header|aside|div|ul|section)>",
    re.I | re.S,
)
_SUBMENU_BLOCK = re.compile(
    r"<ul[^>]*(?:class|id)=[\"'][^\"']*(?:sub-menu|submenu|children|dropdown)[^\"']*[\"'][^>]*>(.*?)</ul>",
    re.I | re.S,
)


def parse_syllabus_intent(query: str) -> dict[str, Any]:
    low = query.lower()
    is_syllabus = "syllabus" in low or (
        bool(_SEM_RE.search(query))
        and any(w in low for w in ("course", "bsc", "b.sc", "m.sc", "program", "subject", "sem", "it", "cs"))
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


def _query_topics(query: str) -> list[str]:
    low = query.lower()
    topics = ["general"]
    for topic, words in _TOPIC_WORDS.items():
        if any(w in low for w in words):
            topics.append(topic)
    return topics


def _same_institution_site(url: str, allowed_hosts: set[str]) -> bool:
    if not allowed_hosts:
        return True
    try:
        host = urlparse(url).netloc.lower().replace("www.", "")
        return any(host == d or host.endswith(f".{d}") for d in allowed_hosts)
    except Exception:
        return False


def _same_site(url: str, root_host: str) -> bool:
    try:
        return urlparse(url).netloc.lower().replace("www.", "") == root_host
    except Exception:
        return False


def _score_nav_link(url: str, label: str, intent: dict[str, Any], depth: int, topics: list[str]) -> int:
    blob = f"{url} {label}".lower()
    blob_ns = blob.replace(" ", "").replace("_", "").replace("-", "")
    score = max(0, 14 - depth * 2)
    contact_focus = "contact" in topics and "syllabus" not in topics
    if _asset_type(url) == "pdf":
        if contact_focus:
            score -= 20
        else:
            score += 14
    for topic in topics:
        words = _TOPIC_WORDS.get(topic, ())
        for w in words:
            if w in blob:
                score += 5
    if not contact_focus:
        for w in _SYLLABUS_WORDS:
            if w.replace(" ", "") in blob_ns or w in blob:
                score += 4
        for w in _NAV_WORDS:
            if w.replace(" ", "") in blob_ns or w in blob:
                score += 3
    for prog in intent.get("programs") or []:
        if prog in blob_ns or prog in blob:
            score += 7
        for hint in _PROGRAM_URL_HINTS.get(prog, ()):
            if hint.replace(" ", "") in blob_ns:
                score += 8
    if "it" in (intent.get("programs") or []) and ("cs" in blob_ns or "computer" in blob):
        score += 4
    sem = intent.get("semester")
    if sem:
        sem_hits = (f"sem{sem}", f"sem-{sem}", f"semester{sem}", f"semester-{sem}", f"sem_{sem}")
        if any(h in blob_ns for h in sem_hits):
            score += 12
    year = intent.get("year")
    if year and year.replace("-", "")[:6] in blob_ns.replace("-", ""):
        score += 5
    if "upload" in blob and _asset_type(url) == "pdf" and not contact_focus:
        score += 6
    if "nep" in blob and not contact_focus:
        score += 4
    if "/pages/" in url or "/academic" in url:
        score += 2
    if contact_focus and any(w in blob for w in ("contact", "address", "location", "map")):
        score += 20
    # Penalize wrong semester in filename when user asked a specific sem.
    sem = intent.get("semester")
    if sem and _asset_type(url) == "pdf":
        wrong = []
        for other in range(1, 9):
            if other == sem:
                continue
            if f"sem{other}" in blob_ns or f"sem-{other}" in blob_ns or f"semester{other}" in blob_ns:
                wrong.append(other)
        if wrong:
            score -= 25
    if is_junk_pdf(label, url):
        score -= 50
    return score


def _extract_links(html: str, page_url: str, nav_bonus: bool = False) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    blocks = [html]
    if nav_bonus:
        for block in _MENU_BLOCK.findall(html):
            blocks.append(block)
        for block in _SUBMENU_BLOCK.findall(html):
            blocks.append(block)
    seen: set[tuple[str, str]] = set()
    for block in blocks:
        for href_raw, inner in _HREF_RE.findall(block):
            href = href_raw.strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            full = urljoin(page_url, href)
            if not full.startswith("http"):
                continue
            label = _clean_text(inner) or full.rsplit("/", 1)[-1]
            key = (full, label)
            if key in seen:
                continue
            seen.add(key)
            items.append((full, label))
    return items


def _min_pdf_score(intent: dict[str, Any]) -> int:
    if intent.get("is_syllabus") and intent.get("semester"):
        return 8
    if intent.get("is_syllabus"):
        return 10
    return 12


def _crawl_limits(is_syllabus: bool, institution: str = "") -> tuple[int, int]:
    custom = get_crawl_limits(institution, is_syllabus)
    if custom:
        return custom
    if is_syllabus:
        return (14, 5)
    if settings.edu_fast_mode:
        return (max(8, settings.edu_site_nav_max_pages // 2), 3)
    return (settings.edu_site_nav_max_pages, settings.edu_site_nav_max_depth)


def _search_pdf_fallbacks(seed_urls: list[str], query: str, intent: dict[str, Any]) -> list[dict[str, Any]]:
    if not seed_urls:
        return []
    host = urlparse(seed_urls[0]).netloc.replace("www.", "")
    prog = " ".join(intent.get("programs") or ["syllabus"])
    sem = f"sem {intent['semester']}" if intent.get("semester") else ""
    year = intent.get("year") or "2024-25"
    queries = [
        f"site:{host} {prog} {sem} {year} syllabus pdf".strip(),
        f"site:{host} {query} syllabus pdf".strip(),
        f"site:{host} upload {prog} sem pdf".strip(),
    ]
    pdfs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for q in queries:
        for r in search_web(q, max_results=5):
            u = r.get("url") or ""
            if ".pdf" not in u.lower() or u in seen:
                continue
            seen.add(u)
            label = r.get("title") or u.rsplit("/", 1)[-1]
            score = _score_nav_link(u, label, intent, 0, _query_topics(query)) + 8
            pdfs.append(
                {
                    "type": "pdf",
                    "url": u,
                    "title": label[:200],
                    "score": score,
                    "source": "search",
                }
            )
    return pdfs


def crawl_official_site(
    seed_urls: list[str],
    query: str,
    institution: str = "",
) -> dict[str, list[dict[str, Any]]]:
    """Priority crawl of menus/sub-menus for official PDFs, pages, and informative images."""
    intent = parse_syllabus_intent(query)
    topics = _query_topics(query)
    max_pages, max_depth = _crawl_limits(intent["is_syllabus"], institution)
    min_pdf = _min_pdf_score(intent)
    allowed_hosts = get_institution_domains(institution) if institution else set()

    pdfs: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    images: list[dict[str, Any]] = []
    visited: set[str] = set()
    heap: list[tuple[int, int, str]] = []

    for url in seed_urls:
        if url:
            heapq.heappush(heap, (-120, 0, url))

    pages_scanned = 0
    while heap and pages_scanned < max_pages:
        _, depth, url = heapq.heappop(heap)
        if url in visited or depth > max_depth:
            continue
        if institution and allowed_hosts and not url_belongs_to_institution(url, institution):
            continue
        visited.add(url)

        if _asset_type(url) == "pdf":
            label = url.rsplit("/", 1)[-1]
            score = _score_nav_link(url, label, intent, depth, topics)
            if score >= min_pdf:
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

        if _asset_type(url) == "image":
            label = url.rsplit("/", 1)[-1]
            score = _score_nav_link(url, label, intent, depth, topics)
            if score >= 5:
                images.append(
                    {
                        "type": "image",
                        "url": url,
                        "title": label,
                        "score": score,
                        "source": "site_nav",
                    }
                )
            continue

        try:
            html = _http_get(url, timeout=10 if intent["is_syllabus"] else 8)
        except Exception:
            continue
        if not html or len(html) < 100:
            continue
        pages_scanned += 1

        for img in _extract_image_assets(html, url, query):
            iu = img.get("url", "")
            if iu and iu not in visited:
                images.append({**img, "source": "site_nav", "score": img.get("score", 5) + 2})

        root_host = urlparse(url).netloc.lower().replace("www.", "")
        for link, label in _extract_links(html, url, nav_bonus=True):
            if institution and not url_belongs_to_institution(link, institution):
                continue
            score = _score_nav_link(link, label, intent, depth + 1, topics)
            link_type = _asset_type(link)
            if link_type == "pdf" and is_junk_pdf(label, link):
                continue
            if link_type == "pdf" and score >= min_pdf:
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
            elif link_type == "image" and score >= 5:
                images.append(
                    {
                        "type": "image",
                        "url": link,
                        "title": label[:200] or link.rsplit("/", 1)[-1],
                        "page": url,
                        "score": score,
                        "source": "site_nav",
                    }
                )
            elif link_type == "page" and score >= 6:
                on_site = (
                    _same_institution_site(link, allowed_hosts)
                    if allowed_hosts
                    else _same_site(link, root_host)
                )
                if on_site:
                    pages.append(
                        {
                            "type": "page",
                            "url": link,
                            "title": label[:200] or link.rsplit("/", 1)[-1],
                            "score": score,
                            "source": "site_nav",
                        }
                    )
                    if depth + 1 <= max_depth and link not in visited:
                        heapq.heappush(heap, (-score, depth + 1, link))

    if len(pdfs) < 3:
        pdfs.extend(_search_pdf_fallbacks(seed_urls, query, intent))

    pdfs.sort(key=lambda x: x.get("score", 0), reverse=True)
    pages.sort(key=lambda x: x.get("score", 0), reverse=True)
    images.sort(key=lambda x: x.get("score", 0), reverse=True)

    def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen_u: set[str] = set()
        out: list[dict[str, Any]] = []
        for item in items:
            u = item.get("url", "")
            if not u or u in seen_u:
                continue
            seen_u.add(u)
            out.append(item)
        return out

    return {
        "pdfs": _dedupe(pdfs)[:8],
        "pages": _dedupe(pages)[:8],
        "images": _dedupe(images)[:6],
    }


def crawl_for_syllabus_pdfs(
    seed_urls: list[str],
    query: str,
    max_pages: int | None = None,
    max_depth: int | None = None,
) -> list[dict[str, Any]]:
    """Backward-compatible wrapper."""
    _ = max_pages, max_depth
    return crawl_official_site(seed_urls, query).get("pdfs", [])
