"""Follow SRKI official Academic → SU Syllabus → UG/PG/PhD menu flow.

Navigation path on https://www.srki.ac.in/:
  Academic → SU SYLLABUS → Under Graduate / Post Graduate / Ph.D. Coursework
Then open the course tab and return the semester PDF links from that section.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote, urljoin

import httpx

from backend.app.config import settings

SU_SYLLABUS_HUB = "https://www.srki.ac.in/pages/su-syllabus/"
UG_SYLLABUS_PAGE = "https://www.srki.ac.in/pages/under-graduate-courses/"
PG_SYLLABUS_PAGE = "https://www.srki.ac.in/pages/post-graduate-courses/"
PHD_SYLLABUS_PAGE = "https://www.srki.ac.in/pages/phd-coursework-paper-iii-amp-iv-/"
# Back-compat aliases used by orchestrator seeds.
_SU_SYLLABUS = SU_SYLLABUS_HUB
_UG = UG_SYLLABUS_PAGE
_PG = PG_SYLLABUS_PAGE
_PHD = PHD_SYLLABUS_PAGE

# Short-name / alias → canonical course label (matched against tab headings).
COURSE_ALIASES: dict[str, str] = {
    "es": "Environmental Science",
    "environmental science": "Environmental Science",
    "environmental": "Environmental Science",
    "env": "Environmental Science",
    "bt": "Biotechnology",
    "biotech": "Biotechnology",
    "biotechnology": "Biotechnology",
    "mb": "Microbiology",
    "microbiology": "Microbiology",
    "micro": "Microbiology",
    "ch": "Chemistry",
    "che": "Chemistry",
    "chemistry": "Chemistry",
    "organic chemistry": "Chemistry",
    "cs": "Computer Science",
    "computer science": "Computer Science",
    "computer": "Computer Science",
    "it": "Information Technology",
    "information technology": "Information Technology",
    "aids": "AIDS",
    "artificial intelligence": "AIDS",
    "data science": "AIDS",
    "ai and data science": "AIDS",
    "ai & data science": "AIDS",
    "mct": "MCT",
    "mobile and cloud": "MCT",
    "mobile and cloud technology": "MCT",
    "ism": "Industrial Safety",
    "industrial safety": "Industrial Safety",
    "genetics": "Genetics",
    "clinical embryology": "Clinical Embryology",
    "pgdmlt": "PGDMLT",
    "mlt": "Medical Laboratory",
}

# Tab pane ids on the UG/PG pages (from official HTML).
_UG_TABS: dict[str, str] = {
    "Biotechnology": "bsc1",
    "Chemistry": "bsc2",
    "Computer Science": "bsc3",
    "Information Technology": "bsc4",
    "Environmental Science": "bsc5",
    "Microbiology": "bsc6",
    "AIDS": "bsc7",
}

_PG_TABS: dict[str, str] = {
    "Biotechnology": "msc1",
    "Chemistry": "msc2",
    "Information Technology": "msc3",
    "Microbiology": "msc5",
    "Industrial Safety": "msc7",
    "Genetics": "msc8",
    "Clinical Embryology": "msc10",
    "AIDS": "msc11",
    "MCT": "msc12",
    "Environmental Science": "msc13",
}


def expand_course_short_names(query: str) -> str:
    """Replace course short names (ES, BT, MB, …) with full names for matching."""
    text = query or ""
    # Longer aliases first so "environmental science" wins over "es".
    for alias, full in sorted(COURSE_ALIASES.items(), key=lambda x: -len(x[0])):
        if " " in alias:
            text = re.sub(re.escape(alias), full, text, flags=re.I)
        else:
            text = re.sub(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", full, text, flags=re.I)
    return text


def detect_course_from_query(query: str) -> str | None:
    low = expand_course_short_names(query).lower()
    for alias, full in sorted(COURSE_ALIASES.items(), key=lambda x: -len(x[0])):
        if re.search(rf"(?<![a-z0-9]){re.escape(full.lower())}(?![a-z0-9])", low):
            return full
        if " " not in alias and re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", (query or "").lower()):
            return full
    return None


def detect_level_from_query(query: str) -> str:
    """Return 'ug', 'pg', 'phd', or 'ug' default for B.Sc.-style queries."""
    low = (query or "").lower()
    if re.search(r"\bph\.?\s*d\.?\b|\bphd\b|coursework", low):
        return "phd"
    if re.search(r"\bm\.?\s*sc\.?\b|\bmsc\b|post\s*graduate|\bpg\b", low):
        return "pg"
    if re.search(r"\bb\.?\s*sc\.?\b|\bbsc\b|under\s*graduate|\bug\b", low):
        return "ug"
    # Bare "ES syllabus" / "BT syllabus" → undergraduate by default at SRKI.
    return "ug"


def _fetch_html(url: str) -> str:
    try:
        with httpx.Client(follow_redirects=True, timeout=20) as client:
            r = client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; SRKI-EduBot/1.0)"})
            r.raise_for_status()
            return r.text
    except Exception:
        return ""


def _extract_pane_html(html: str, pane_id: str) -> str:
    m = re.search(
        rf'<div[^>]*\bid=["\']{re.escape(pane_id)}["\'][^>]*>(.*?)</div>\s*<div[^>]*\bid=',
        html,
        re.I | re.S,
    )
    if m:
        return m.group(1)
    # Last pane: capture until end of tab-content / next major block.
    m = re.search(
        rf'<div[^>]*\bid=["\']{re.escape(pane_id)}["\'][^>]*>(.*?)(?:</div>\s*</div>\s*</div>|$)',
        html,
        re.I | re.S,
    )
    return m.group(1) if m else ""


def _pdfs_from_html(chunk: str, page_url: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in re.finditer(
        r'<a\b[^>]*href=["\']([^"\']+\.pdf)["\'][^>]*>(.*?)</a>',
        chunk,
        re.I | re.S,
    ):
        href = urljoin(page_url, m.group(1).strip())
        label = re.sub(r"<[^>]+>|&nbsp;?", " ", m.group(2)).strip()
        label = re.sub(r"\s+", " ", label)
        out.append(
            {
                "type": "pdf",
                "url": href,
                "title": label or unquote(href.rsplit("/", 1)[-1]),
                "source": "srki_syllabus_nav",
                "curated": True,
                "page": page_url,
            }
        )
    return out


def _score_pdf(query: str, course: str | None, item: dict[str, Any]) -> int:
    low = expand_course_short_names(query).lower()
    blob = f"{item.get('url', '')} {item.get('title', '')}".lower()
    blob = unquote(blob)
    # Baseline above generic curated PDFs so menu-nav results win.
    score = 100

    sem_req = None
    for n in range(1, 9):
        if re.search(rf"\bsem(?:ester)?[\s\-]*{n}\b", low):
            sem_req = n
            break
    title = (item.get("title") or "").lower()
    if sem_req is not None:
        if re.search(rf"\bsem(?:ester)?[\s\-]*{sem_req}\b|sem[\s\-]*{sem_req}\b", title + " " + blob):
            score += 50
        elif re.search(r"\bsem(?:ester)?[\s\-]*[1-8]\b", title + " " + blob):
            score -= 40

    if course:
        c = course.lower()
        if c in blob or any(a in blob for a, f in COURSE_ALIASES.items() if f == course and len(a) <= 3):
            score += 40
        # ES curriculum folder / filenames
        if course == "Environmental Science" and (
            "environmental" in blob
            or "b-sc-es" in blob
            or "b.sc-es" in blob
            or "es-syll" in blob
            or " es_" in blob
            or "(b-sc-es" in blob
        ):
            score += 45
        if course == "Biotechnology" and ("biotech" in blob or "biotechnology" in blob):
            score += 40
        if course == "Microbiology" and ("microbiology" in blob or " mb" in blob or "/mb" in blob):
            score += 40

    if "2025-26" in blob or "2024-25" in blob:
        score += 8
    if "hons" in blob and "hons" in low:
        score += 5
    # Prefer course-specific PDFs over shared merged packs when both match.
    if "merged" in blob or "bt-ch-mb" in blob or "bt-ch-es-mb" in blob:
        score -= 25
    return score


def navigate_srki_syllabus(query: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Walk official SU Syllabus menus and return matching PDF resources + portal pages."""
    course = detect_course_from_query(query)
    level = detect_level_from_query(query)
    resources: list[dict[str, Any]] = []
    portals: list[str] = [_SU_SYLLABUS]

    if level == "phd":
        portals.append(_PHD)
        html = _fetch_html(_PHD)
        for item in _pdfs_from_html(html, _PHD):
            item["score"] = 120
            item["title"] = f"Official Ph.D. coursework — {item['title']}"
            resources.append(item)
    else:
        page = _UG if level == "ug" else _PG
        portals.append(page)
        html = _fetch_html(page)
        tabs = _UG_TABS if level == "ug" else _PG_TABS
        pane_id = tabs.get(course or "") if course else None
        chunks: list[tuple[str, str]] = []
        if pane_id:
            pane = _extract_pane_html(html, pane_id)
            if pane:
                chunks.append((pane, course or ""))
        if not chunks:
            # Fallback: whole page (still better than nothing).
            chunks.append((html, course or ""))

        for chunk, _c in chunks:
            for item in _pdfs_from_html(chunk, page):
                item["score"] = _score_pdf(query, course, item)
                fname = unquote(item["url"].rsplit("/", 1)[-1])
                item["title"] = f"Official syllabus — {item['title']} ({fname})"
                resources.append(item)

    # Always expose the navigation portals as high-priority pages.
    portal_resources = [
        {
            "type": "page",
            "url": _SU_SYLLABUS,
            "title": "SRKI — SU Syllabus hub (Academic → SU SYLLABUS)",
            "score": 210,
            "source": "srki_syllabus_nav",
            "is_portal": True,
            "curated": True,
        }
    ]
    if level == "ug":
        portal_resources.append(
            {
                "type": "page",
                "url": _UG,
                "title": "SRKI — Under Graduate Courses syllabus (official)",
                "score": 208,
                "source": "srki_syllabus_nav",
                "is_portal": True,
                "curated": True,
            }
        )
    elif level == "pg":
        portal_resources.append(
            {
                "type": "page",
                "url": _PG,
                "title": "SRKI — Post Graduate Courses syllabus (official)",
                "score": 208,
                "source": "srki_syllabus_nav",
                "is_portal": True,
                "curated": True,
            }
        )
    else:
        portal_resources.append(
            {
                "type": "page",
                "url": _PHD,
                "title": "SRKI — Ph.D. Coursework (Paper III & IV)",
                "score": 208,
                "source": "srki_syllabus_nav",
                "is_portal": True,
                "curated": True,
            }
        )

    resources.sort(key=lambda x: x.get("score", 0), reverse=True)
    # Keep strong matches only.
    pdfs = [r for r in resources if r.get("type") == "pdf"]
    if pdfs:
        best = pdfs[0]["score"]
        pdfs = [r for r in pdfs if r["score"] >= max(best - 55, 50)][:6]
    return portal_resources + pdfs, portals


def format_course_resolution_note(query: str) -> str:
    course = detect_course_from_query(query)
    if not course:
        return ""
    raw = (query or "").lower()
    shorts = [a for a, f in COURSE_ALIASES.items() if f == course and " " not in a and re.search(rf"\b{re.escape(a)}\b", raw)]
    if shorts:
        return f"Interpreted **{shorts[0].upper()}** as **{course}**."
    return f"Course: **{course}**."
