"""Constituent colleges, parent universities, and regional institution networks."""

from __future__ import annotations

import re
from typing import Any

# Canonical institution names used across orchestrator / official_links.
SRKI = "Shree Ramkrishna Institute of Computer Education and Applied Sciences"
SU = "Sarvajanik University"
VNSGU = "Veer Narmad South Gujarat University"
GTU = "Gujarat Technological University"

# Alias (lowercase) -> canonical institution name.
CONSTITUENT_ALIASES: dict[str, str] = {
    "srki": SRKI,
    "shree ramkrishna institute": SRKI,
    "shree ramkrishna": SRKI,
    "ramkrishna institute": SRKI,
    "sarvajanik university": SU,
    "sarvajanik": SU,
    "su surat": SU,
    "vnsgu": VNSGU,
    "veer narmad south gujarat university": VNSGU,
    "veer narmad": VNSGU,
    "south gujarat university": VNSGU,
    "gtu": GTU,
    "gujarat technological university": GTU,
    "gujarat technological": GTU,
    "svnit": "Sardar Vallabhbhai National Institute of Technology Surat",
    # SU constituent short names
    "scet": "Sarvajanik College of Engineering and Technology",
    "sarvajanik college of engineering": "Sarvajanik College of Engineering and Technology",
    "scol": "Sarvajanik College of Law",
    "sarvajanik college of law": "Sarvajanik College of Law",
    "brcm": "B.R.C.M. College of Business Administration",
    "brcm college": "B.R.C.M. College of Business Administration",
    "sccca": "Sarvajanik College of Commerce and Computer Applications",
    "srlim": "Smt. Shardarani Rameshchander Luthra Institute of Management",
    "scopa": "Shri Pankaj Kapadia Sarvajanik College of Performing Arts",
    "sctcc": "Sarvajanik Centre for Training and Certificate Courses",
    "idpt": "Institute of Design, Planning and Technology",
    "idpt scet": "Institute of Design, Planning and Technology",
}

# Parent university for constituent colleges.
PARENT_UNIVERSITY: dict[str, str] = {
    SRKI: SU,
    "Sarvajanik College of Engineering and Technology": SU,
    "Sarvajanik College of Law": SU,
    "B.R.C.M. College of Business Administration": SU,
    "Sarvajanik College of Commerce and Computer Applications": SU,
    "Smt. Shardarani Rameshchander Luthra Institute of Management": SU,
    "Shri Pankaj Kapadia Sarvajanik College of Performing Arts": SU,
    "Sarvajanik Centre for Training and Certificate Courses": SU,
    "Institute of Design, Planning and Technology": SU,
}

VNSGU_AFFILIATED_ALIASES: dict[str, str] = {
    "government engineering college surat": VNSGU,
    "gec surat": VNSGU,
    "bhagwan mahavir college": VNSGU,
    "bcp": VNSGU,
    "bharatiya vidya bhavan": VNSGU,
}

SU_CONSTITUENT_ALIASES: dict[str, str] = {
    "srki": SRKI,
    "shree ramkrishna institute": SRKI,
    "scet": "Sarvajanik College of Engineering and Technology",
    "scol": "Sarvajanik College of Law",
    "brcm": "B.R.C.M. College of Business Administration",
    "sccca": "Sarvajanik College of Commerce and Computer Applications",
    "srlim": "Smt. Shardarani Rameshchander Luthra Institute of Management",
    "scopa": "Shri Pankaj Kapadia Sarvajanik College of Performing Arts",
    "sctcc": "Sarvajanik Centre for Training and Certificate Courses",
    "idpt": "Institute of Design, Planning and Technology",
}

# Gujarat / Surat context — auto-map bare "SU" to Sarvajanik University.
_SU_REGION_HINTS = (
    "surat",
    "gujarat",
    "srki",
    "sarvajanik",
    "scet",
    "scol",
    "brcm",
    "sccca",
    "srlim",
    "scopa",
    "sctcc",
    "idpt",
    "constituent",
    "nep",
)

# Constituent college metadata: domains and entry URLs for menu crawl.
SU_CONSTITUENT_SITES: list[dict[str, Any]] = [
    {
        "canonical": SRKI,
        "domains": ("srki.ac.in",),
        "urls": (
            "https://www.srki.ac.in/",
            "https://www.srki.ac.in/pages/su-syllabus/",
            "https://www.srki.ac.in/pages/admission-corner/",
            "https://www.srki.ac.in/pages/courses-offered/",
        ),
    },
    {
        "canonical": SU,
        "domains": ("sarvajanikuniversity.ac.in", "sarvajanikuniversity.edu.in"),
        "urls": (
            "https://www.sarvajanikuniversity.ac.in/",
            "https://sarvajanikuniversity.ac.in/aboutus/",
            "https://sarvajanikuniversity.ac.in/admission/",
        ),
    },
    {
        "canonical": "Sarvajanik College of Engineering and Technology",
        "domains": ("scet.ac.in", "sarvajanikuniversity.ac.in"),
        "urls": ("https://www.scet.ac.in/",),
    },
    {
        "canonical": "Sarvajanik College of Law",
        "domains": ("sarvajanikuniversity.ac.in", "sarvajaniklaw.org"),
        "urls": ("https://sarvajanikuniversity.ac.in/",),
    },
    {
        "canonical": "B.R.C.M. College of Business Administration",
        "domains": ("brcmbba.org", "sarvajanikuniversity.ac.in"),
        "urls": ("https://www.brcmbba.org/",),
    },
    {
        "canonical": "Sarvajanik College of Commerce and Computer Applications",
        "domains": ("sarvajanikuniversity.ac.in",),
        "urls": ("https://sarvajanikuniversity.ac.in/aboutus/",),
    },
    {
        "canonical": "Smt. Shardarani Rameshchander Luthra Institute of Management",
        "domains": ("sarvajanikuniversity.ac.in",),
        "urls": ("https://sarvajanikuniversity.ac.in/aboutus/",),
    },
]

VNSGU_OFFICIAL_SEEDS: tuple[str, ...] = (
    "https://www.vnsgu.ac.in/",
    "https://www.vnsguj.ac.in/",
    "https://vnsgu.ac.in/Syllabus/",
    "https://www.vnsgu.ac.in/external_examination",
    "https://www.vnsguj.ac.in/affiliated_colleges.php",
    "https://vnsguadm.samarth.edu.in/",
)

GTU_OFFICIAL_SEEDS: tuple[str, ...] = (
    "https://gtu.ac.in/syllabus/syllabus.aspx",
    "https://www.gtu.ac.in/syllabus/syllabus.aspx",
    "https://www.gtu.ac.in/",
    "https://gtu.ac.in/StudyMaterial.aspx",
    "https://www.gtu.ac.in/StudyMaterial.aspx",
)

_SORTED_ALIAS_ITEMS = sorted(
    {**CONSTITUENT_ALIASES, **VNSGU_AFFILIATED_ALIASES, **SU_CONSTITUENT_ALIASES}.items(),
    key=lambda x: len(x[0]),
    reverse=True,
)


def is_su_gujarat_context(query: str) -> bool:
    low = query.lower()
    return any(h in low for h in _SU_REGION_HINTS)


def resolve_bare_su(query: str) -> str | None:
    """Map standalone SU to Sarvajanik University when Gujarat/Surat context is present."""
    if not re.search(r"\bsu\b", query, re.I):
        return None
    if is_su_gujarat_context(query):
        return SU
    return None


def resolve_constituent(query: str) -> str | None:
    """Match constituent college / university short names in a query (longest alias first)."""
    low = query.lower()
    for alias, canonical in _SORTED_ALIAS_ITEMS:
        if len(alias) < 2:
            continue
        if re.search(rf"\b{re.escape(alias)}\b", low):
            return canonical
    su = resolve_bare_su(query)
    if su:
        return su
    return None


def get_parent_university(institution: str) -> str:
    return PARENT_UNIVERSITY.get(institution, "")


def is_su_network(institution: str) -> bool:
    if not institution:
        return False
    if institution == SU:
        return True
    return get_parent_university(institution) == SU


def is_vnsgu_network(institution: str) -> bool:
    if not institution:
        return False
    return institution == VNSGU or institution in VNSGU_AFFILIATED_ALIASES.values()


def is_gtu_network(institution: str) -> bool:
    return institution == GTU


def is_srki_network(institution: str) -> bool:
    return institution == SRKI or is_su_network(institution)


def get_extra_domains(institution: str) -> set[str]:
    """Additional allowed domains beyond official_links catalog."""
    domains: set[str] = set()
    if is_su_network(institution):
        for site in SU_CONSTITUENT_SITES:
            if institution == SU or site["canonical"] == institution:
                domains.update(site["domains"])
        if institution == SU:
            for site in SU_CONSTITUENT_SITES:
                domains.update(site["domains"])
    if is_vnsgu_network(institution):
        domains.update(
            d.replace("www.", "")
            for d in (
                "vnsgu.ac.in",
                "vnsguj.ac.in",
                "vnsguadm.samarth.edu.in",
                "vnsgu.net",
            )
        )
    if is_gtu_network(institution):
        domains.add("gtu.ac.in")
    return domains


def get_crawl_seed_urls(institution: str, base_urls: list[str], query: str = "") -> list[str]:
    """Merge curated seeds with constituent-college entry pages for deep menu crawl."""
    seeds: list[str] = list(base_urls)
    low = (query or "").lower()

    if is_su_network(institution):
        for site in SU_CONSTITUENT_SITES:
            if institution == SU or site["canonical"] == institution:
                seeds.extend(site["urls"])
        if institution == SU and any(w in low for w in ("constituent", "college", "list")):
            seeds.append("https://sarvajanikuniversity.ac.in/aboutus/")

    if is_vnsgu_network(institution):
        seeds.extend(VNSGU_OFFICIAL_SEEDS)

    if is_gtu_network(institution):
        seeds.extend(GTU_OFFICIAL_SEEDS)

    # Dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for u in seeds:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def get_crawl_limits(institution: str, is_syllabus: bool) -> tuple[int, int]:
    """Higher crawl depth for priority regional institutions."""
    priority = is_su_network(institution) or is_vnsgu_network(institution) or is_gtu_network(institution)
    if is_syllabus:
        if priority:
            return (18, 5)
        return (14, 5)
    if priority:
        return (12, 4)
    return (10, 3)
