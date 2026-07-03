"""Curated official website links when live web search is unavailable (e.g. on cloud hosts)."""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Canonical institution name -> topic -> official URLs (verified university domains).
INSTITUTION_OFFICIAL_LINKS: dict[str, dict[str, list[str]]] = {
    "Veer Narmad South Gujarat University": {
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
            "https://www.vnsgu.ac.in/",
            "https://www.vnsguj.ac.in/",
        ],
        "academics": [
            "https://www.vnsgu.ac.in/",
            "https://www.vnsguj.ac.in/affiliated_colleges.php",
        ],
    },
    "Shree Ramkrishna Institute of Computer Education and Applied Sciences": {
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
    },
    "Gujarat Technological University": {
        "default": ["https://www.gtu.ac.in/"],
        "admission": ["https://www.gtu.ac.in/admission.aspx"],
        "syllabus": [
            "https://www.gtu.ac.in/syllabus.aspx",
            "https://www.gtu.ac.in/StudyMaterial.aspx",
            "https://www.gtu.ac.in/AllCourses.aspx",
        ],
        "academics": [
            "https://www.gtu.ac.in/syllabus.aspx",
            "https://www.gtu.ac.in/StudyMaterial.aspx",
        ],
    },
    "Sardar Vallabhbhai National Institute of Technology Surat": {
        "default": ["https://www.svnit.ac.in/"],
        "admission": ["https://www.svnit.ac.in/admission"],
    },
    "Sarvajanik University": {
        "default": ["https://www.sarvajanikuniversity.edu.in/"],
        "syllabus": ["https://www.sarvajanikuniversity.edu.in/"],
        "academics": ["https://www.sarvajanikuniversity.edu.in/"],
        "admission": ["https://www.sarvajanikuniversity.edu.in/"],
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
    topics = ["default"]
    for topic, words in _TOPIC_KEYWORDS.items():
        if any(w in low for w in words):
            topics.append(topic)
    # Preserve order, unique
    seen: set[str] = set()
    out: list[str] = []
    for t in topics:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def get_official_urls(institution: str, query: str = "") -> list[str]:
    """Return deduplicated official URLs for a named institution."""
    catalog = INSTITUTION_OFFICIAL_LINKS.get(institution)
    if not catalog:
        return []
    urls: list[str] = []
    seen: set[str] = set()
    for topic in _topics_for_query(query):
        for url in catalog.get(topic, []):
            if url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def get_official_search_results(institution: str, query: str = "") -> list[dict]:
    """Shape curated links like web-search results for grounding."""
    results: list[dict] = []
    for url in get_official_urls(institution, query):
        host = re.sub(r"^www\.", "", url.split("//")[-1].split("/")[0])
        label = f"{institution} — {host}"
        if "admission" in query.lower() or "admission" in url.lower():
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
    "Shree Ramkrishna Institute of Computer Education and Applied Sciences": ("srki.ac.in",),
    "Sarvajanik University": ("sarvajanikuniversity.edu.in", "srki.ac.in"),
    "Gujarat Technological University": ("gtu.ac.in",),
    "Veer Narmad South Gujarat University": ("vnsgu.ac.in", "vnsguj.ac.in", "vnsguadm.samarth.edu.in", "vnsgu.net"),
    "Sardar Vallabhbhai National Institute of Technology Surat": ("svnit.ac.in",),
}

_JUNK_PDF_TITLE = re.compile(
    r"^(view(\s*\(\d+\))?(\.pdf)?|click\s*here\.+|download|here\.+|\.pdf)$",
    re.I,
)


def get_institution_domains(institution: str) -> set[str]:
    domains: set[str] = set(_INSTITUTION_DOMAIN_HINTS.get(institution, ()))
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
