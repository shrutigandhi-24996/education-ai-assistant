"""Fetch and cache text from official SRKI / related web pages."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from backend.app.config import settings

DEFAULT_SEEDS = [
    "https://www.srki.ac.in/",
    "https://www.srki.ac.in/pages/admission-corner/",
    "https://www.srki.ac.in/contact/",
    "https://www.srki.ac.in/pages/srki-constituent-college-of-sarvajanik-university-/",
    "https://www.srki.ac.in/pages/history/",
]

ALLOWED_HOSTS = ("srki.ac.in", "www.srki.ac.in")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "nav", "footer", "header"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer", "header"} and self._skip:
            self._skip -= 1
        if tag in {"p", "h1", "h2", "h3", "h4", "li", "td", "th", "div"} and not self._skip:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self._chunks.append(data.strip())

    def text(self) -> str:
        raw = " ".join(self._chunks)
        raw = re.sub(r"\s+", " ", raw)
        return raw.strip()


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    # SRKI site returns 404 without trailing slash on many /pages/... URLs
    if not path.endswith("/") and ("/pages/" in path or path in {"/contact"}):
        path = f"{path}/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _allowed(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


def fetch_html(url: str, timeout: int = 15) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": settings.web_user_agent,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text()


_SKIP_SUFFIXES = (
    ".css",
    ".js",
    ".jpeg",
    ".jpg",
    ".png",
    ".gif",
    ".webp",
    ".woff",
    ".woff2",
    ".pdf",
    ".ico",
    ".svg",
)


def _is_content_page(url: str) -> bool:
    lower = url.lower()
    if any(lower.endswith(ext) for ext in _SKIP_SUFFIXES):
        return False
    if "/theme/" in lower or "/upload/gallery" in lower or "/assets/" in lower:
        return False
    return True


def extract_links(html: str, base_url: str) -> list[str]:
    links: list[str] = []
    for match in re.finditer(r'href=["\']([^"\']+)["\']', html, re.I):
        href = match.group(1).strip()
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        full = urljoin(base_url, href)
        if not _allowed(full) or not full.startswith("http"):
            continue
        full = _normalize_url(full.split("#")[0])
        if _is_content_page(full):
            links.append(full)
    return list(dict.fromkeys(links))


def chunk_text(text: str, size: int = 900, overlap: int = 120) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    step = max(1, (size - overlap) // 5)
    i = 0
    while i < len(words):
        piece = " ".join(words[i : i + size])
        if len(piece) > 80:
            chunks.append(piece)
        i += step
    return chunks


def scrape_site(
    seed_urls: Iterable[str] | None = None,
    max_pages: int | None = None,
) -> list[dict]:
    seeds = [_normalize_url(u) for u in (seed_urls or settings.web_seed_urls_list())]
    max_pages = max_pages or settings.web_max_pages
    seen: set[str] = set()
    queue: list[str] = []
    pages: list[dict] = []

    def scrape_one(url: str) -> str | None:
        nonlocal pages
        if url in seen:
            return None
        seen.add(url)
        try:
            html = fetch_html(url, timeout=settings.web_request_timeout)
            text = html_to_text(html)
            if len(text) < 60:
                return html
            title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
            title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else url
            if re.search(r"\b404\b", title, re.I) or "404-error" in text[:200].lower():
                return html
            pages.append(
                {
                    "url": url,
                    "title": title,
                    "text": text,
                    "chunks": chunk_text(text),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            time.sleep(settings.web_request_delay_sec)
            return html
        except Exception as exc:
            pages.append(
                {
                    "url": url,
                    "title": url,
                    "text": "",
                    "chunks": [],
                    "error": str(exc),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            return None

    seed_html: list[tuple[str, str]] = []
    for seed in seeds:
        html = scrape_one(seed)
        if html:
            seed_html.append((seed, html))

    for seed, html in seed_html:
        for link in extract_links(html, seed):
            if link not in seen and link not in queue:
                queue.append(link)

    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        html = scrape_one(url)
        if html:
            for link in extract_links(html, url):
                if link not in seen and link not in queue:
                    queue.append(link)
    return pages


def save_cache(pages: list[dict], cache_dir: Path | None = None) -> Path:
    out = cache_dir or settings.web_cache_dir
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "page_count": len(pages),
        "pages": pages,
    }
    path = out / "srki_web_cache.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def cache_is_fresh(cache_dir: Path | None = None) -> bool:
    path = (cache_dir or settings.web_cache_dir) / "srki_web_cache.json"
    if not path.exists():
        return False
    age_hours = (time.time() - path.stat().st_mtime) / 3600
    return age_hours <= settings.web_cache_ttl_hours


def load_cache(cache_dir: Path | None = None) -> list[dict]:
    path = (cache_dir or settings.web_cache_dir) / "srki_web_cache.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("pages") or []


def refresh_cache_if_needed(force: bool = False) -> int:
    if not settings.web_scrape_enabled:
        return 0
    if not force and cache_is_fresh():
        return len(load_cache())
    pages = scrape_site()
    save_cache(pages)
    return len([p for p in pages if p.get("chunks")])
