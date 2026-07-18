"""Download official PDFs and extract text for grounded chat answers."""

from __future__ import annotations

import io
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from backend.app.config import settings
from backend.app.pipeline.web_search import _is_official_url

_MAX_BYTES = 8 * 1024 * 1024
_MAX_PAGES = 8
_MAX_CHARS = 4500 if settings.edu_fast_mode else 7000
_PDF_PATH = re.compile(r"\.pdf(\?|#|$)", re.I)


def is_allowed_pdf_url(url: str) -> bool:
    """Only proxy official or .pdf URLs to reduce abuse."""
    if not url.startswith(("http://", "https://")):
        return False
    parsed = urlparse(url)
    if not parsed.netloc:
        return False
    if _PDF_PATH.search(url):
        return True
    return _is_official_url(url)


def _http_get_bytes(url: str, timeout: int) -> bytes:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/pdf,application/octet-stream,*/*",
    }
    resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    data = resp.content
    if len(data) > _MAX_BYTES:
        raise ValueError("PDF too large")
    return data


def fetch_pdf_for_view(url: str) -> tuple[bytes, str]:
    """Fetch PDF bytes for same-origin inline viewing (bypasses X-Frame-Options)."""
    if not is_allowed_pdf_url(url):
        raise ValueError("PDF URL not allowed")
    timeout = 12 if settings.edu_fast_mode else 18
    data = _http_get_bytes(url, timeout=timeout)
    if not data.startswith(b"%PDF"):
        raise ValueError("Remote file is not a PDF")
    return data, "application/pdf"


def _course_keywords_from_query(query: str) -> tuple[str, ...]:
    low = (query or "").lower()
    mapping = (
        (("microbiology", " mb "), ("microbiology", "microbial", "bacteriology", "prokaryotic", "nutrition and growth of bacteria")),
        (("biotechnology", " biotech", " bt "), ("biotechnology", "biotech", "plant anatomy", "animal physiology")),
        (("chemistry", " che "), ("chemistry", "organic chemistry", "analytical chemistry", "inorganic chemistry")),
        (("environmental", " es "), ("environmental science", "environmental", "ecology", "ecosystem")),
        (("computer science", " cs "), ("computer science", "programming", "python", "data structure")),
        (("information technology", " it "), ("information technology", "database", "web technology")),
        (("aids", "data science", "artificial intelligence"), ("artificial intelligence", "data science", "machine learning")),
    )
    for q_hints, keys in mapping:
        if any(h.strip() in low for h in q_hints):
            return keys
    return ()


def extract_text_from_pdf_bytes(
    data: bytes,
    max_pages: int = _MAX_PAGES,
    max_chars: int = _MAX_CHARS,
    query: str = "",
) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception:
        return ""

    keywords = _course_keywords_from_query(query)
    page_texts: list[tuple[int, str]] = []
    for idx, page in enumerate(reader.pages[: max(max_pages * 3, 24)]):
        try:
            text = (page.extract_text() or "").strip()
        except Exception:
            continue
        if not text:
            continue
        page_texts.append((idx, text))

    if keywords and page_texts:
        # Prefer pages that mention the requested course (merged BT/CH/MB PDFs).
        primary = keywords[0]
        scored = []
        for idx, text in page_texts:
            low = text.lower()
            hit = sum(3 if k == primary else 1 for k in keywords if k in low)
            # Strong boost when the course name appears as a programme heading.
            if re.search(rf"\b{re.escape(primary)}\b", low):
                hit += 5
            if "b.sc" in low or "bsc" in low:
                hit += 1
            scored.append((hit, -idx, text))
        scored.sort(reverse=True)
        if scored and scored[0][0] > 0:
            page_texts = [(0, t) for _, _, t in scored[:max_pages]]

    parts: list[str] = []
    total = 0
    for _, text in page_texts[:max_pages]:
        parts.append(text)
        total += len(text)
        if total >= max_chars:
            break

    merged = re.sub(r"\s+", " ", " ".join(parts)).strip()
    if len(merged) > max_chars:
        merged = merged[:max_chars].rsplit(" ", 1)[0] + "…"
    return merged


def read_pdf_from_url(url: str, title: str = "", query: str = "") -> dict[str, Any]:
    """Fetch a PDF and return extracted text plus metadata."""
    timeout = 10 if settings.edu_fast_mode else 18
    try:
        data = _http_get_bytes(url, timeout=timeout)
    except Exception as exc:
        return {"url": url, "title": title or url.rsplit("/", 1)[-1], "text": "", "error": str(exc)}

    text = extract_text_from_pdf_bytes(data, query=query)
    return {
        "url": url,
        "title": title or url.rsplit("/", 1)[-1],
        "text": text,
        "pages_read": min(_MAX_PAGES, 8),
    }


def enrich_pdf_resources(
    resources: list[dict[str, Any]],
    query: str,
    max_pdfs: int = 2,
    institution: str = "",
) -> list[dict[str, Any]]:
    """Extract text from the most relevant PDF resources (in parallel)."""
    from backend.app.pipeline.official_links import filter_resources_for_institution, is_junk_pdf

    pdfs = [r for r in resources if r.get("type") == "pdf"]
    if institution:
        pdfs = filter_resources_for_institution(pdfs, institution)
    pdfs = [r for r in pdfs if not is_junk_pdf(r.get("title", ""), r.get("url", ""))]
    if not pdfs:
        return [r for r in resources if r.get("type") != "pdf"]

    # Prefer high score; among near-ties, prefer course-complete NEP packs for cleaner extracts.
    pdfs.sort(
        key=lambda r: (
            r.get("score", 0),
            1 if "complete" in (r.get("url") or "").lower() else 0,
        ),
        reverse=True,
    )
    to_read = pdfs[:max_pdfs]

    from concurrent.futures import ThreadPoolExecutor, as_completed

    extracted: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max_pdfs) as pool:
        futures = {
            pool.submit(read_pdf_from_url, r["url"], r.get("title", ""), query): r["url"]
            for r in to_read
        }
        for fut in as_completed(futures):
            url = futures[fut]
            try:
                result = fut.result()
                if result.get("text"):
                    extracted[url] = result["text"]
            except Exception:
                pass

    out: list[dict[str, Any]] = []
    for r in resources:
        item = dict(r)
        text = extracted.get(r.get("url", ""))
        if text:
            item["extract"] = text
            item["has_content"] = True
        out.append(item)
    return out


def format_pdf_context_blocks(resources: list[dict[str, Any]]) -> list[str]:
    """Build WEB CONTEXT blocks from PDF text extracts."""
    blocks: list[str] = []
    for r in resources:
        if r.get("type") != "pdf":
            continue
        text = (r.get("extract") or "").strip()
        if not text:
            continue
        title = r.get("title") or r.get("url", "PDF")
        url = r.get("url", "")
        blocks.append(
            f"[OFFICIAL-PDF-CONTENT] {title}\n"
            f"Extracted text from official PDF (use for specific facts; cite this PDF link):\n"
            f"{text}\n"
            f"Direct PDF link: {url}"
        )
    return blocks
