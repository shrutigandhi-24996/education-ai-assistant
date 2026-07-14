"""Curated official website links when live web search is unavailable (e.g. on cloud hosts)."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from backend.app.pipeline.institution_catalog import (
    GTU,
    SRKI,
    SU,
    VNSGU,
    get_crawl_seed_urls,
    get_extra_domains,
    is_gtu_network,
    is_su_network,
)

# Canonical institution name -> topic -> official URLs (verified university domains).
INSTITUTION_OFFICIAL_LINKS: dict[str, dict[str, list[str]]] = {
    VNSGU: {
        "default": [
            "https://www.vnsgu.ac.in/",
            "https://www.vnsguj.ac.in/",
        ],
        "admission": [
            "https://vnsguadm.samarth.edu.in/",
            "https://vnsguadm.samarth.edu.in/index.php/site/index",
            "https://admission.vnsgu.net/Student/QuickRegistration.aspx",
        ],
        "contact": [
            "https://vnsguj.ac.in/contact_us.php",
        ],
        "syllabus": [
            "https://vnsgu.ac.in/Syllabus/",
            "https://www.vnsgu.ac.in/",
            "https://www.vnsguj.ac.in/",
            "https://www.vnsgu.ac.in/external_examination",
        ],
        "academics": [
            "https://vnsgu.ac.in/Syllabus/",
            "https://www.vnsguj.ac.in/affiliated_colleges.php",
            "https://www.vnsgu.ac.in/",
        ],
        "exam": [
            "https://www.vnsgu.ac.in/external_examination",
        ],
        "syllabus_pdfs": [
            "https://vnsgu.ac.in/Syllabus/Syllabus/Syllabus%20(2024-2025)/Computer%20Science/UG/BCA%20Artificial%20Intelligence%20&%20Data%20Analytics%20(Honours)%20Sem%201%20&%202%20Syllabus%20from%202024-25%20(dt%2029-05-2024).pdf",
            "https://vnsgu.ac.in/uploads/syllabus/Syllabus%20(2025-2026)/Computer%20Science/UG/B.Sc.(Data%20Science%20and%20Analytics)Sem.-3%20&%204%20Syllabus%202025-26_(16-06-2025).pdf",
        ],
        "syllabus_portal": [
            "https://vnsgu.ac.in/Syllabus/",
        ],
    },
    SRKI: {
        "default": ["https://www.srki.ac.in/"],
        "admission": ["https://www.srki.ac.in/pages/admission-corner/"],
        "syllabus": [
            "https://www.srki.ac.in/pages/su-syllabus/",
            "https://www.srki.ac.in/pages/courses-offered/",
            "https://www.srki.ac.in/pages/srki-constituent-college-of-sarvajanik-university-/",
        ],
        "academics": [
            "https://www.srki.ac.in/pages/su-syllabus/",
            "https://www.srki.ac.in/pages/courses-offered/",
        ],
        "syllabus_pdfs": [
            "https://www.srki.ac.in/upload/2024-25/NEP_BSc_CS_Sem1_Syllabus_CS_2024-25-1-16.pdf",
            "https://www.srki.ac.in/upload/2024-25/NEP_BSc_IT_Sem1_Syllabus_IT_2024-25.pdf",
            "https://www.srki.ac.in/upload/2022-23/B.Sc%20IT.pdf",
        ],
        "syllabus_portal": [
            "https://www.srki.ac.in/pages/su-syllabus/",
        ],
    },
    "Gujarat Technological University": {
        "default": ["https://www.gtu.ac.in/", "https://gtu.ac.in/"],
        "admission": [
            "https://www.gtu.ac.in/admission.aspx",
            "https://gtu.ac.in/admission.aspx",
        ],
        "syllabus": [
            "https://gtu.ac.in/syllabus/syllabus.aspx",
            "https://www.gtu.ac.in/syllabus/syllabus.aspx",
            "https://www.gtu.ac.in/StudyMaterial.aspx",
            "https://gtu.ac.in/StudyMaterial.aspx",
        ],
        "academics": [
            "https://gtu.ac.in/syllabus/syllabus.aspx",
            "https://www.gtu.ac.in/syllabus/syllabus.aspx",
            "https://www.gtu.ac.in/AllCourses.aspx",
        ],
        "syllabus_portal": [
            "https://gtu.ac.in/syllabus/syllabus.aspx",
        ],
    },
    "Sardar Vallabhbhai National Institute of Technology Surat": {
        "default": ["https://www.svnit.ac.in/"],
        "admission": ["https://www.svnit.ac.in/admission"],
    },
    "Sarvajanik University": {
        "default": [
            "https://www.sarvajanikuniversity.ac.in/",
            "https://sarvajanikuniversity.ac.in/aboutus/",
        ],
        "syllabus": [
            "https://www.srki.ac.in/pages/su-syllabus/",
            "https://www.sarvajanikuniversity.ac.in/",
            "https://sarvajanikuniversity.ac.in/aboutus/",
        ],
        "academics": [
            "https://sarvajanikuniversity.ac.in/aboutus/",
            "https://www.srki.ac.in/pages/courses-offered/",
        ],
        "admission": [
            "https://www.sarvajanikuniversity.ac.in/",
            "https://www.srki.ac.in/pages/admission-corner/",
        ],
        "syllabus_portal": [
            "https://www.srki.ac.in/pages/su-syllabus/",
            "https://sarvajanikuniversity.ac.in/aboutus/",
        ],
    },
    "Sarvajanik College of Engineering and Technology": {
        "default": ["https://www.scet.ac.in/"],
        "admission": ["https://www.scet.ac.in/"],
        "syllabus": ["https://www.scet.ac.in/", "https://www.srki.ac.in/pages/su-syllabus/"],
        "academics": ["https://www.scet.ac.in/"],
    },
    "B.R.C.M. College of Business Administration": {
        "default": ["https://www.brcmbba.org/"],
        "admission": ["https://www.brcmbba.org/"],
        "syllabus": ["https://www.brcmbba.org/"],
    },
}

_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "admission": ("admission", "admissions", "apply", "application", "eligibility", "2026", "2025"),
    "contact": ("contact", "address", "phone", "email"),
    "syllabus": ("syllabus", "curriculum", "sem", "semester", "scheme", "regulation", "nep", "course"),
    "academics": ("academic", "academics", "department", "program", "programme", "faculty"),
}


def _topics_for_query(query: str) -> list[str]:
    low = query.lower()
    matched: list[str] = []
    for topic, words in _TOPIC_KEYWORDS.items():
        if any(w in low for w in words):
            matched.append(topic)
    if not matched:
        return ["default"]
    seen: set[str] = set()
    out: list[str] = []
    for t in matched + ["default"]:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def get_syllabus_portal_urls(institution: str, query: str = "") -> list[str]:
    """Primary official syllabus selection / download pages (shown first in chat)."""
    catalog = INSTITUTION_OFFICIAL_LINKS.get(institution, {})
    portals = list(catalog.get("syllabus_portal") or [])
    if not portals and "syllabus" in _topics_for_query(query):
        portals = [u for u in catalog.get("syllabus", []) if "syllabus" in u.lower()]
    seen: set[str] = set()
    out: list[str] = []
    for u in portals:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def get_portal_page_resources(institution: str, query: str = "") -> list[dict]:
    """High-priority official portal pages for syllabus/admission queries."""
    low = query.lower()
    is_syllabus = any(w in low for w in _TOPIC_KEYWORDS["syllabus"])
    if not is_syllabus:
        return []
    resources: list[dict] = []
    for url in get_syllabus_portal_urls(institution, query):
        if institution == GTU:
            title = "GTU official syllabus portal — select course & semester"
        elif institution == SRKI:
            title = "SRKI official syllabus page (Sarvajanik University)"
        elif institution == SU:
            title = "Sarvajanik University syllabus & constituent colleges"
        elif institution == VNSGU:
            title = "VNSGU official syllabus section"
        else:
            title = f"{institution} official syllabus page"
        resources.append(
            {
                "type": "page",
                "url": url,
                "title": title,
                "score": 200,
                "source": "curated_portal",
                "is_portal": True,
                "curated": True,
            }
        )
    return resources


def get_official_urls(institution: str, query: str = "") -> list[str]:
    """Return deduplicated official URLs for a named institution."""
    catalog = INSTITUTION_OFFICIAL_LINKS.get(institution)
    urls: list[str] = []
    seen: set[str] = set()
    if catalog:
        for topic in _topics_for_query(query):
            for url in catalog.get(topic, []):
                if url not in seen:
                    seen.add(url)
                    urls.append(url)
    # SU / GTU / VNSGU parent queries also surface deep official entry pages.
    if is_su_network(institution) or is_gtu_network(institution):
        urls = get_crawl_seed_urls(institution, urls, query)
    elif institution == VNSGU:
        urls = get_crawl_seed_urls(institution, urls, query)
    return urls


def get_official_search_results(institution: str, query: str = "") -> list[dict]:
    """Shape curated links like web-search results for grounding."""
    results: list[dict] = []
    low = query.lower()
    is_syllabus = any(w in low for w in _TOPIC_KEYWORDS["syllabus"])

    # Syllabus portal pages first (matches Google-style official syllabus hub).
    for r in get_portal_page_resources(institution, query):
        results.append(
            {
                "title": r["title"],
                "url": r["url"],
                "snippet": (
                    f"Official syllabus portal for {institution}. "
                    "Open this page to select course, branch, and semester — same as the university website."
                ),
                "extract": (
                    f"Official syllabus selection portal for {institution}: {r['url']}. "
                    "Use this page to find the correct syllabus PDF or scheme for the requested program/semester."
                ),
                "curated": True,
                "is_portal": True,
            }
        )

    seen = {r["url"] for r in results}
    for url in get_official_urls(institution, query):
        if url in seen:
            continue
        seen.add(url)
        host = re.sub(r"^www\.", "", url.split("//")[-1].split("/")[0])
        label = f"{institution} — {host}"
        if is_syllabus and "syllabus" in url.lower():
            label = f"{institution} — official syllabus page ({host})"
        elif "admission" in low or "admission" in url.lower():
            label = f"{institution} — official admission portal ({host})"
        results.append(
            {
                "title": label,
                "url": url,
                "snippet": f"Official website link for {institution}. Verify admissions, fees, and dates here.",
                "extract": f"Official source for {institution}: {url}",
                "curated": True,
            }
        )
    return results


# Known domain roots per institution (used to block cross-college URL mixing).
_INSTITUTION_DOMAIN_HINTS: dict[str, tuple[str, ...]] = {
    SRKI: ("srki.ac.in",),
    SU: ("sarvajanikuniversity.ac.in", "sarvajanikuniversity.edu.in", "srki.ac.in", "scet.ac.in"),
    "Sarvajanik College of Engineering and Technology": ("scet.ac.in", "sarvajanikuniversity.ac.in"),
    "B.R.C.M. College of Business Administration": ("brcmbba.org", "sarvajanikuniversity.ac.in"),
    "Gujarat Technological University": ("gtu.ac.in",),
    VNSGU: ("vnsgu.ac.in", "vnsguj.ac.in", "vnsguadm.samarth.edu.in", "vnsgu.net"),
    "Sardar Vallabhbhai National Institute of Technology Surat": ("svnit.ac.in",),
}

_JUNK_PDF_TITLE = re.compile(
    r"^(view(\s*\(\d+\))?(\.pdf)?|click\s*here\.+|download|here\.+|\.pdf)$",
    re.I,
)


def get_institution_domains(institution: str) -> set[str]:
    domains: set[str] = set(_INSTITUTION_DOMAIN_HINTS.get(institution, ()))
    domains.update(get_extra_domains(institution))
    catalog = INSTITUTION_OFFICIAL_LINKS.get(institution, {})
    for urls in catalog.values():
        for url in urls:
            host = urlparse(url).netloc.lower().replace("www.", "")
            if host:
                domains.add(host)
    return domains


def url_belongs_to_institution(url: str, institution: str) -> bool:
    if not institution or not url:
        return True
    domains = get_institution_domains(institution)
    if not domains:
        return True
    host = urlparse(url).netloc.lower().replace("www.", "")
    return any(host == d or host.endswith(f".{d}") for d in domains)


def is_junk_pdf(title: str, url: str) -> bool:
    name = (title or url.rsplit("/", 1)[-1]).strip()
    if not name or len(name) < 4:
        return True
    if _JUNK_PDF_TITLE.match(name):
        return True
    low = name.lower()
    if low.startswith("click here") or low == "view" or low.startswith("view "):
        return True
    return False


def get_curated_pdf_results(institution: str, query: str = "") -> list[dict]:
    """Return curated official PDF links for an institution (syllabus etc.)."""
    catalog = INSTITUTION_OFFICIAL_LINKS.get(institution, {})
    pdfs = catalog.get("syllabus_pdfs") or []
    low = query.lower()
    out: list[dict] = []
    for url in pdfs:
        label = url.rsplit("/", 1)[-1]
        score = 20
        if "sem1" in low or "sem 1" in low or "sem-1" in low:
            if "sem1" in label.lower() or "sem-1" in label.lower() or "_1_" in label.lower():
                score += 15
            if "sem2" in label.lower() or "sem-2" in label.lower():
                score -= 20
        if "sem2" in low or "sem 2" in low or "sem-2" in low:
            if "sem2" in label.lower() or "sem-2" in label.lower():
                score += 15
            if "sem1" in label.lower():
                score -= 20
        if "it" in low.split() and "it" in label.lower():
            score += 10
        if "bca" in low and "bca" in label.lower():
            score += 10
        if "bsc" in low and "b.sc" in label.lower():
            score += 8
        if "data science" in low and "data" in label.lower():
            score += 8
        if "2025-26" in label or "2025" in label:
            score += 6
        if "2024-25" in label or "2024" in label:
            score += 5
        out.append(
            {
                "type": "pdf",
                "url": url,
                "title": label,
                "score": score,
                "source": "curated",
                "curated": True,
            }
        )
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


def filter_urls_for_institution(urls: list[str], institution: str) -> list[str]:
    if not institution:
        return urls
    return [u for u in urls if url_belongs_to_institution(u, institution)]


def filter_resources_for_institution(resources: list[dict], institution: str) -> list[dict]:
    if not institution:
        return resources
    out: list[dict] = []
    for r in resources:
        url = r.get("url", "")
        if r.get("type") == "pdf" and is_junk_pdf(r.get("title", ""), url):
            continue
        if url_belongs_to_institution(url, institution):
            out.append(r)
    return out
