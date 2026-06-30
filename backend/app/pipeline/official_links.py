"""Curated official website links when live web search is unavailable (e.g. on cloud hosts)."""

from __future__ import annotations

import re

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
    },
    "Shree Ramkrishna Institute of Computer Education and Applied Sciences": {
        "default": ["https://www.srki.ac.in/"],
        "admission": ["https://www.srki.ac.in/pages/admission-corner/"],
    },
    "Gujarat Technological University": {
        "default": ["https://www.gtu.ac.in/"],
        "admission": ["https://www.gtu.ac.in/admission.aspx"],
    },
    "Sardar Vallabhbhai National Institute of Technology Surat": {
        "default": ["https://www.svnit.ac.in/"],
        "admission": ["https://www.svnit.ac.in/admission"],
    },
}

_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "admission": ("admission", "admissions", "apply", "application", "eligibility", "2026", "2025"),
    "contact": ("contact", "address", "phone", "email"),
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
