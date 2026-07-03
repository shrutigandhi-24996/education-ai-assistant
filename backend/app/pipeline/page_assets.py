"""Extract PDFs, documents, images, and relevant page links from official HTML pages."""

from __future__ import annotations

import re
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse

from backend.app.config import settings

from backend.app.pipeline.web_search import _http_get, _is_official_url

_FILE_PDF = re.compile(r"\.pdf(\?|#|$)", re.I)
_FILE_DOC = re.compile(r"\.(doc|docx|xls|xlsx|ppt|pptx)(\?|#|$)", re.I)
_FILE_IMG = re.compile(r"\.(jpg|jpeg|png|gif|webp|bmp|svg)(\?|#|$)", re.I)
_HREF_RE = re.compile(r'<a\b[^>]*\bhref=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
_IMG_SRC_RE = re.compile(
    r'<img\b[^>]*\bsrc=["\']([^"\']+)["\'][^>]*(?:\balt=["\']([^"\']*)["\'])?',
    re.I | re.S,
)
_TAG = re.compile(r"<[^>]+>")
_DECORATIVE_IMG = re.compile(r"(logo|icon|banner|sprite|avatar|favicon|arrow|button)", re.I)

_TOPIC_HINTS: dict[str, tuple[str, ...]] = {
    "admission": ("admission", "admit", "apply", "application", "prospectus", "brochure", "entrance"),
    "fee": ("fee", "fees", "tuition", "charges", "cost"),
    "syllabus": ("syllabus", "curriculum", "scheme", "regulation", "credit"),
    "department": ("department", "dept", "faculty", "school of", "institute of"),
    "course": ("course", "program", "programme", "b.sc", "b.tech", "m.sc", "mba", "bca", "mca"),
    "exam": ("exam", "result", "timetable", "schedule", "notification"),
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(_TAG.sub(" ", value))).strip()


def _asset_type(url: str) -> str:
    low = url.lower()
    if _FILE_PDF.search(low):
        return "pdf"
    if _FILE_DOC.search(low):
        return "document"
    if _FILE_IMG.search(low):
        return "image"
    return "page"


def _score_link(url: str, label: str, query: str) -> int:
    blob = f"{url} {label}".lower()
    score = 0
    qterms = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]
    for t in qterms:
        if t in blob:
            score += 3
    for words in _TOPIC_HINTS.values():
        if any(w in blob for w in words):
            score += 2
    if _FILE_PDF.search(url):
        score += 4
    if _FILE_DOC.search(url):
        score += 3
    if _FILE_IMG.search(url):
        score += 2
    if _is_official_url(url):
        score += 5
    if "blog" in blob:
        score -= 8
    if _DECORATIVE_IMG.search(blob):
        score -= 6
    return score


def _extract_image_assets(html: str, page_url: str, query: str) -> list[dict[str, Any]]:
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    page_title = _clean_text(title_m.group(1)) if title_m else page_url
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in _IMG_SRC_RE.finditer(html):
        src = match.group(1).strip()
        alt = _clean_text(match.group(2) or "")
        if not src or src.startswith("data:"):
            continue
        full = urljoin(page_url, src)
        if not full.startswith("http") or full in seen:
            continue
        if not _FILE_IMG.search(full):
            continue
        label = alt or full.rsplit("/", 1)[-1]
        if _DECORATIVE_IMG.search(label) or _DECORATIVE_IMG.search(full):
            continue
        score = _score_link(full, label, query)
        if score < 3:
            continue
        seen.add(full)
        items.append(
            {
                "type": "image",
                "url": full,
                "title": label[:200],
                "page": page_url,
                "page_title": page_title[:200],
                "score": score,
            }
        )
    items.sort(key=lambda x: x["score"], reverse=True)
    return items[:4]


def extract_assets_from_html(html: str, page_url: str, query: str, max_items: int = 10) -> list[dict[str, Any]]:
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    page_title = _clean_text(title_m.group(1)) if title_m else page_url
    seen: set[str] = set()
    items: list[dict[str, Any]] = []

    for href_raw, inner in _HREF_RE.findall(html):
        href = href_raw.strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full = urljoin(page_url, href)
        if not full.startswith("http"):
            continue
        label = _clean_text(inner) or full.rsplit("/", 1)[-1]
        atype = _asset_type(full)
        score = _score_link(full, label, query)

        if atype in ("pdf", "document", "image"):
            pass
        elif atype == "page" and score < 4:
            continue
        elif atype == "page" and urlparse(full).netloc != urlparse(page_url).netloc:
            continue

        if full in seen:
            continue
        seen.add(full)
        items.append(
            {
                "type": atype,
                "url": full,
                "title": label[:200],
                "page": page_url,
                "page_title": page_title[:200],
                "score": score,
            }
        )

    items.sort(key=lambda x: x["score"], reverse=True)
    img_items = _extract_image_assets(html, page_url, query)
    merged = items + [i for i in img_items if i["url"] not in seen]
    merged.sort(key=lambda x: x["score"], reverse=True)
    return merged[:max_items]


def fetch_page_assets(page_url: str, query: str, max_items: int = 10) -> list[dict[str, Any]]:
    if _asset_type(page_url) in ("pdf", "document"):
        name = page_url.rsplit("/", 1)[-1]
        return [
            {
                "type": _asset_type(page_url),
                "url": page_url,
                "title": name,
                "page": page_url,
                "page_title": name,
                "score": 10,
            }
        ]
    try:
        html = _http_get(page_url, timeout=6 if settings.edu_fast_mode else 12)
    except Exception:
        return []
    if not html or len(html) < 100:
        return []
    return extract_assets_from_html(html, page_url, query, max_items=max_items)


def harvest_official_assets(seed_urls: list[str], query: str, max_pages: int = 3) -> list[dict[str, Any]]:
    """Scan official HTML pages for PDFs, docs, images, and relevant sub-pages."""
    all_items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    pages_scanned = 0

    for url in seed_urls:
        if pages_scanned >= max_pages:
            break
        batch = fetch_page_assets(url, query, max_items=5 if settings.edu_fast_mode else 8)
        if _asset_type(url) == "page":
            pages_scanned += 1
        for item in batch:
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            all_items.append(item)

    type_order = {"pdf": 0, "document": 1, "page": 2, "image": 3}
    all_items.sort(key=lambda x: (type_order.get(x["type"], 9), -x["score"]))
    return all_items[:6 if settings.edu_fast_mode else 10]
