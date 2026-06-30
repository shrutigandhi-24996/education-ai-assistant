"""General web search for out-of-scope / external-institution queries.

Uses DuckDuckGo's HTML endpoint (no API key required) so the assistant can
answer questions about other universities (e.g. VNSGU) or unseen topics with
grounded, source-cited snippets instead of hallucinating.
"""
from __future__ import annotations

import hashlib
import html as html_lib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen

from backend.app.config import settings
from backend.app.pipeline.web_scraper import html_to_text

_HTML_ENDPOINT = "https://html.duckduckgo.com/html/?q={q}"
_LITE_ENDPOINT = "https://lite.duckduckgo.com/lite/?q={q}"

# html.duckduckgo.com uses class="result__a" / "result__snippet";
# lite.duckduckgo.com uses class='result-link' / 'result-snippet'.
_RESULT_LINK = re.compile(
    r'<a\b([^>]*\bclass=["\'](?:result__a|result-link)["\'][^>]*)>(.*?)</a>',
    re.I | re.S,
)
_HREF = re.compile(r'href=["\']([^"\']+)["\']', re.I)
_RESULT_SNIPPET = re.compile(
    r'class=["\'](?:result__snippet|result-snippet)["\'][^>]*>(.*?)</(?:a|td)>',
    re.I | re.S,
)
_OFFICIAL_HOST = re.compile(
    r"(\.edu|\.gov|\.ac\.[a-z]{2,3}|\.edu\.[a-z]{2,3}|\.gov\.[a-z]{2,3}|"
    r"\.ac\.in|\.edu\.in|\.nic\.in|\.res\.in)$"
)
_TAG = re.compile(r"<[^>]+>")


def _is_official_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower().split(":")[0]
    except Exception:
        return False
    return bool(_OFFICIAL_HOST.search(host))


def _rank_results(results: list[dict]) -> list[dict]:
    return sorted(results, key=lambda r: (0 if _is_official_url(r.get("url", "")) else 1))


def _strip_tags(value: str) -> str:
    return html_lib.unescape(_TAG.sub("", value)).strip()


def _decode_ddg_href(href: str) -> str:
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        qs = parse_qs(parsed.query)
        target = qs.get("uddg", [None])[0]
        if target:
            return unquote(target)
    return href


def _http_get(url: str, timeout: int) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": settings.web_user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def _parse_results(html: str, limit: int) -> list[dict]:
    results: list[dict] = []
    snippets = [_strip_tags(s) for s in _RESULT_SNIPPET.findall(html)]
    for i, (attrs, title) in enumerate(_RESULT_LINK.findall(html)):
        href_match = _HREF.search(attrs)
        if not href_match:
            continue
        url = _decode_ddg_href(href_match.group(1))
        if not url.startswith("http"):
            continue
        snippet = snippets[i] if i < len(snippets) else ""
        results.append(
            {
                "title": _strip_tags(title),
                "url": url,
                "snippet": snippet,
            }
        )
        if len(results) >= limit:
            break
    return results


def search_web(query: str, max_results: int | None = None) -> list[dict]:
    """Return a list of {title, url, snippet} for a free-text query."""
    limit = max_results or settings.external_search_max_results
    timeout = settings.external_search_timeout
    q = quote_plus(query)
    for endpoint in (_HTML_ENDPOINT, _LITE_ENDPOINT):
        try:
            html = _http_get(endpoint.format(q=q), timeout=timeout)
        except Exception:
            continue
        results = _parse_results(html, limit)
        if results:
            return results
    return []


def fetch_page_extract(url: str, query: str, max_len: int = 900) -> str:
    """Fetch a result page and return the most query-relevant passage."""
    try:
        html = _http_get(url, timeout=settings.external_search_timeout)
    except Exception:
        return ""
    text = html_to_text(html)
    if len(text) < 80:
        return ""
    terms = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 3]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    best, best_score = "", -1
    window = ""
    for sent in sentences:
        window = (window + " " + sent).strip()[-max_len * 2 :]
        score = sum(window.lower().count(t) for t in terms)
        if score > best_score:
            best_score, best = score, window
    snippet = (best or text)[:max_len].strip()
    return snippet


def _cache_path(query: str) -> Path:
    key = hashlib.sha1(query.lower().strip().encode("utf-8")).hexdigest()[:16]
    return settings.external_search_cache_dir / f"{key}.json"


def _load_cached(query: str) -> list[dict] | None:
    path = _cache_path(query)
    if not path.exists():
        return None
    age_hours = (time.time() - path.stat().st_mtime) / 3600
    if age_hours > settings.external_search_cache_ttl_hours:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("results")
    except Exception:
        return None


def _save_cached(query: str, results: list[dict]) -> None:
    try:
        settings.external_search_cache_dir.mkdir(parents=True, exist_ok=True)
        with open(_cache_path(query), "w", encoding="utf-8") as f:
            json.dump(
                {"query": query, "updated_at": datetime.now(timezone.utc).isoformat(), "results": results},
                f,
                ensure_ascii=False,
                indent=2,
            )
    except Exception:
        pass


def search_with_grounding(query: str, institution: str | None = None) -> dict:
    """Search the web and return grounded results with optional page extracts.

    Returns {"results": [...], "grounded": bool}. Each result may carry an
    "extract" pulled directly from the source page to reduce hallucination.
    """
    cached = _load_cached(query)
    if cached is not None:
        return {"results": cached, "grounded": bool(cached), "cached": True}

    results = search_web(query)
    results = _rank_results(results)
    fetch_n = min(settings.external_search_fetch_pages, len(results))
    for r in results[:fetch_n]:
        extract = fetch_page_extract(r["url"], query)
        if extract:
            r["extract"] = extract
    _save_cached(query, results)
    return {"results": results, "grounded": bool(results), "cached": False}
