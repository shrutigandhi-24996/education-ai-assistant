"""Constituent colleges, parent universities, and regional institution networks."""

from __future__ import annotations

import re
from typing import Any

# Canonical institution names used across orchestrator / official_links.
SRKI = "Shree Ramkrishna Institute of Computer Education and Applied Sciences"
SU = "Sarvajanik University"
VNSGU = "Veer Narmad South Gujarat University"
GTU = "Gujarat Technological University"

SCET = "Sarvajanik College of Engineering and Technology"
SCOL = "Sarvajanik College of Law"
BRCM = "B.R.C.M. College of Business Administration"
SCCCA = "KP Human Sarvajanik College of Commerce and Computer Applications"
SRLIM = "Smt. Shardarani Rameshchander Luthra Institute of Management"
SCOPA = "Shri Pankaj Kapadia Sarvajanik College of Performing Arts"
SCTCC = "Sarvajanik Centre for Training and Certificate Courses"
IDPT = "MITRAJ Sarvajanik Institute of Design, Planning and Technology"
SCLA = "Sarvajanik College of Liberal Arts"

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
    "scet": SCET,
    "sarvajanik college of engineering": SCET,
    "scol": SCOL,
    "sarvajanik college of law": SCOL,
    "brcm": BRCM,
    "brcm college": BRCM,
    "sccca": SCCCA,
    "kp human": SCCCA,
    "srlim": SRLIM,
    "scopa": SCOPA,
    "sctcc": SCTCC,
    "idpt": IDPT,
    "idpt scet": IDPT,
    "mitraj": IDPT,
    "scla": SCLA,
    "liberal arts": SCLA,
}

PARENT_UNIVERSITY: dict[str, str] = {
    SRKI: SU,
    SCET: SU,
    SCOL: SU,
    BRCM: SU,
    SCCCA: SU,
    SRLIM: SU,
    SCOPA: SU,
    SCTCC: SU,
    IDPT: SU,
    SCLA: SU,
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
    "scet": SCET,
    "scol": SCOL,
    "brcm": BRCM,
    "sccca": SCCCA,
    "srlim": SRLIM,
    "scopa": SCOPA,
    "sctcc": SCTCC,
    "idpt": IDPT,
    "scla": SCLA,
}

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
    "scla",
    "mitraj",
    "kp human",
    "constituent",
    "nep",
)

# Official SRKI pages for menu/sub-menu crawl (syllabus hub + department pages).
SRKI_OFFICIAL_SEEDS: tuple[str, ...] = (
    "https://www.srki.ac.in/",
    "https://www.srki.ac.in/pages/su-syllabus/",
    "https://www.srki.ac.in/pages/under-graduate-courses/",
    "https://www.srki.ac.in/pages/post-graduate-courses/",
    "https://www.srki.ac.in/pages/phd-coursework-paper-iii-amp-iv-/",
    "https://www.srki.ac.in/pages/admission-corner/",
    "https://www.srki.ac.in/pages/courses-offered/",
    "https://www.srki.ac.in/pages/srki-constituent-college-of-sarvajanik-university-/",
    "https://www.srki.ac.in/contact/",
    "https://www.srki.ac.in/pages/fees-structure/",
    "https://www.srki.ac.in/pages/fees-payment/",
    "https://www.srki.ac.in/pages/fees-payment-notice/",
    "https://www.srki.ac.in/pages/history/",
    "https://www.srki.ac.in/department/computer-science/",
    "https://www.srki.ac.in/department/microbiology/",
    "https://www.srki.ac.in/department/biotechnology/",
    "https://www.srki.ac.in/department/environmental-science/",
    "https://www.srki.ac.in/department/chemistry/",
)

# Course → department page (official syllabus PDFs live under department menus).
SRKI_DEPARTMENT_BY_COURSE: dict[str, str] = {
    "computer science": "https://www.srki.ac.in/department/computer-science/",
    "cs": "https://www.srki.ac.in/department/computer-science/",
    "information technology": "https://www.srki.ac.in/department/computer-science/",
    "it": "https://www.srki.ac.in/department/computer-science/",
    "aids": "https://www.srki.ac.in/department/computer-science/",
    "artificial intelligence": "https://www.srki.ac.in/department/computer-science/",
    "data science": "https://www.srki.ac.in/department/computer-science/",
    "microbiology": "https://www.srki.ac.in/department/microbiology/",
    "mb": "https://www.srki.ac.in/department/microbiology/",
    "biotechnology": "https://www.srki.ac.in/department/biotechnology/",
    "bt": "https://www.srki.ac.in/department/biotechnology/",
    "environmental science": "https://www.srki.ac.in/department/environmental-science/",
    "es": "https://www.srki.ac.in/department/environmental-science/",
    "chemistry": "https://www.srki.ac.in/department/chemistry/",
    "che": "https://www.srki.ac.in/department/chemistry/",
    "organic chemistry": "https://www.srki.ac.in/department/chemistry/",
}


def get_srki_department_urls_for_query(query: str) -> list[str]:
    """Return the SRKI department page(s) that match the course named in the query."""
    low = (query or "").lower()
    # Prefer longer / more specific keys first.
    keys = sorted(SRKI_DEPARTMENT_BY_COURSE.keys(), key=len, reverse=True)
    out: list[str] = []
    for key in keys:
        if re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", low):
            url = SRKI_DEPARTMENT_BY_COURSE[key]
            if url not in out:
                out.append(url)
    return out

SU_PARENT_SEEDS: tuple[str, ...] = (
    "https://www.sarvajanikuniversity.ac.in/",
    "https://sarvajanikuniversity.ac.in/aboutus/",
    "https://student.sarvajanikuniversity.ac.in:8080/admissionindex.html",
    "https://www.sarvajanikuniversity.ac.in/pages/advertisement-sarvajanik-college-of-liberal-arts/",
)

# Constituent college metadata: domains and entry URLs for menu crawl.
SU_CONSTITUENT_SITES: list[dict[str, Any]] = [
    {
        "canonical": SRKI,
        "domains": ("srki.ac.in",),
        "urls": SRKI_OFFICIAL_SEEDS,
    },
    {
        "canonical": SU,
        "domains": ("sarvajanikuniversity.ac.in", "sarvajanikuniversity.edu.in", "student.sarvajanikuniversity.ac.in"),
        "urls": SU_PARENT_SEEDS,
    },
    {
        "canonical": SCET,
        "domains": ("scet.ac.in",),
        "urls": ("https://www.scet.ac.in/", "https://www.scet.ac.in/academics/"),
    },
    {
        "canonical": SCOL,
        "domains": ("sarvajaniklaw.org",),
        "urls": ("https://sarvajaniklaw.org/",),
    },
    {
        "canonical": BRCM,
        "domains": ("brcmbba.org",),
        "urls": ("https://www.brcmbba.org/",),
    },
    {
        "canonical": SCCCA,
        "domains": ("sccca.ac.in",),
        "urls": ("https://www.sccca.ac.in/",),
    },
    {
        "canonical": SRLIM,
        "domains": ("srlimba.ac.in",),
        "urls": ("https://srlimba.ac.in/",),
    },
    {
        "canonical": SCOPA,
        "domains": ("scopa-surat.ac.in",),
        "urls": ("https://www.scopa-surat.ac.in/",),
    },
    {
        "canonical": IDPT,
        "domains": ("idpt-scet.ac.in",),
        "urls": ("https://www.idpt-scet.ac.in/",),
    },
    {
        "canonical": SCTCC,
        "domains": ("sarvajanikuniversity.ac.in",),
        "urls": ("https://sarvajanikuniversity.ac.in/aboutus/",),
    },
    {
        "canonical": SCLA,
        "domains": ("sarvajanikuniversity.ac.in",),
        "urls": (
            "https://www.sarvajanikuniversity.ac.in/pages/advertisement-sarvajanik-college-of-liberal-arts/",
        ),
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


def all_su_constituent_domains() -> set[str]:
    domains: set[str] = set()
    for site in SU_CONSTITUENT_SITES:
        domains.update(site["domains"])
    return domains


def get_constituent_primary_domain(institution: str) -> str | None:
    for site in SU_CONSTITUENT_SITES:
        if site["canonical"] == institution and site["domains"]:
            return site["domains"][0]
    return None


def is_su_gujarat_context(query: str) -> bool:
    low = query.lower()
    return any(h in low for h in _SU_REGION_HINTS)


def resolve_bare_su(query: str) -> str | None:
    if not re.search(r"\bsu\b", query, re.I):
        return None
    if is_su_gujarat_context(query):
        return SU
    return None


def resolve_constituent(query: str) -> str | None:
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


def is_srki_only(institution: str) -> bool:
    return institution == SRKI


def is_vnsgu_network(institution: str) -> bool:
    if not institution:
        return False
    return institution == VNSGU or institution in VNSGU_AFFILIATED_ALIASES.values()


def is_gtu_network(institution: str) -> bool:
    return institution == GTU


def is_srki_network(institution: str) -> bool:
    return institution == SRKI or is_su_network(institution)


def get_extra_domains(institution: str) -> set[str]:
    domains: set[str] = set()
    if is_su_network(institution):
        for site in SU_CONSTITUENT_SITES:
            if institution == SU:
                domains.update(site["domains"])
            elif site["canonical"] == institution:
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
    seeds: list[str] = list(base_urls)
    low = (query or "").lower()

    if institution == SRKI:
        # Put the matching department page first so syllabus PDFs are harvested early.
        seeds.extend(get_srki_department_urls_for_query(query))
        seeds.extend(SRKI_OFFICIAL_SEEDS)
    elif is_su_network(institution):
        for site in SU_CONSTITUENT_SITES:
            if institution == SU or site["canonical"] == institution:
                seeds.extend(site["urls"])
        if institution == SU:
            seeds.extend(SU_PARENT_SEEDS)
            if any(w in low for w in ("constituent", "college", "list", "all")):
                seeds.append("https://sarvajanikuniversity.ac.in/aboutus/")

    if is_vnsgu_network(institution):
        seeds.extend(VNSGU_OFFICIAL_SEEDS)
    if is_gtu_network(institution):
        seeds.extend(GTU_OFFICIAL_SEEDS)

    seen: set[str] = set()
    out: list[str] = []
    for u in seeds:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def get_crawl_limits(institution: str, is_syllabus: bool) -> tuple[int, int]:
    priority = (
        is_srki_only(institution)
        or institution == SU
        or is_su_network(institution)
        or is_vnsgu_network(institution)
        or is_gtu_network(institution)
    )
    if is_syllabus:
        if priority:
            return (22, 5)
        return (14, 5)
    if priority:
        return (14, 4)
    return (10, 3)


def get_asset_harvest_pages(institution: str) -> int:
    """More official pages scanned for SRKI / SU network queries."""
    if is_srki_only(institution) or institution == SU:
        return 8
    if is_su_network(institution):
        return 6
    return 3


def is_constituent_list_query(query: str) -> bool:
    low = (query or "").lower()
    return any(
        p in low
        for p in (
            "constituent college",
            "constituent colleges",
            "colleges under",
            "list of college",
            "list of colleges",
            "affiliated college",
        )
    )


_COURSE_LIST_PATTERNS = (
    "courses offered",
    "course offered",
    "offered courses",
    "which courses",
    "what courses",
    "list of courses",
    "list of course",
    "courses list",
    "course list",
    "available courses",
    "courses available",
    "which programs",
    "which programmes",
    "programs offered",
    "programmes offered",
    "degrees offered",
    "courses does",
    "courses do",
)


def is_courses_offered_query(query: str) -> bool:
    """True for 'which courses does X offer / list of courses' style queries."""
    low = (query or "").lower()
    if not any(p in low for p in _COURSE_LIST_PATTERNS):
        return False
    # Let the full pipeline handle mixed questions (fees/syllabus/admission details).
    if any(w in low for w in ("syllabus", "fee", "fees", "admission", "eligibility", "merit")):
        return False
    return True


# Verified from https://www.srki.ac.in/pages/courses-offered/ (official page).
_SRKI_UG_COURSES = (
    ("Biotechnology", "90 seats"),
    ("Chemistry", "30 seats"),
    ("Computer Science", "30 seats"),
    ("Information Technology", "140 seats"),
    ("Environmental Science", "30 seats"),
    ("Microbiology", "120 seats"),
    ("Artificial Intelligence & Data Science (AIDS)", "70 seats"),
)

_SRKI_PG_COURSES = (
    "M.Sc. Biotechnology",
    "M.Sc. Organic Chemistry",
    "M.Sc. AI and Data Science",
    "M.Sc. Information Technology",
    "M.Sc. Mobile and Cloud Technology",
    "M.Sc. Environmental Science",
    "M.Sc. Environmental Science (Industrial Safety and Environmental Management)",
    "M.Sc. Microbiology",
    "M.Sc. Industrial Microbiology",
    "M.Sc. Medical Laboratory Technology",
    "M.Sc. Clinical Embryology",
    "PGDMLT (PG Diploma in Medical Laboratory Technology)",
)

_SRKI_COURSES_PAGE = "https://www.srki.ac.in/pages/courses-offered/"

_SRKI_DEPARTMENT_PAGES = (
    ("Computer Science", "https://www.srki.ac.in/department/computer-science/"),
    ("Microbiology", "https://www.srki.ac.in/department/microbiology/"),
    ("Biotechnology", "https://www.srki.ac.in/department/biotechnology/"),
    ("Environmental Science", "https://www.srki.ac.in/department/environmental-science/"),
    ("Chemistry", "https://www.srki.ac.in/department/chemistry/"),
)


def format_srki_courses_answer() -> tuple[str, list[dict], list[str]]:
    """Curated complete list of SRKI courses from the official courses-offered page."""
    lines = [
        "**Courses offered by SRKI** (Shree Ramkrishna Institute of Computer Education and "
        "Applied Sciences, Surat)",
        "",
        f"Official courses page: [srki.ac.in/pages/courses-offered]({_SRKI_COURSES_PAGE})",
        "",
        "**Undergraduate — B.Sc. / B.Sc. (Hons.), 3/4 years (6 or 8 semesters):**",
    ]
    for i, (name, seats) in enumerate(_SRKI_UG_COURSES, 1):
        lines.append(f"{i}. B.Sc./B.Sc.(Hons.) {name} — {seats}")
    lines.append("")
    lines.append("**Postgraduate:**")
    for i, name in enumerate(_SRKI_PG_COURSES, 1):
        lines.append(f"{i}. {name}")
    lines.append("")
    lines.append(
        "Each course's duration, intake, eligibility, and brochure are on the "
        f"[official courses page]({_SRKI_COURSES_PAGE}). "
        "For admissions, apply via the [Sarvajanik University admission portal]"
        "(https://student.sarvajanikuniversity.ac.in:8080/admissionindex.html)."
    )

    resources: list[dict] = [
        {
            "type": "page",
            "url": _SRKI_COURSES_PAGE,
            "title": "SRKI — official Courses Offered page (details, eligibility & brochures)",
            "score": 220,
            "source": "curated_portal",
            "is_portal": True,
            "curated": True,
        }
    ]
    for name, url in _SRKI_DEPARTMENT_PAGES:
        resources.append(
            {
                "type": "page",
                "url": url,
                "title": f"SRKI — {name} department",
                "score": 90,
                "source": "curated",
                "curated": True,
            }
        )
    sources = [_SRKI_COURSES_PAGE, "https://www.srki.ac.in/"]
    return "\n".join(lines), resources, sources


def format_su_constituent_colleges_answer() -> tuple[str, list[dict], list[str]]:
    """Curated accurate list of SU constituent colleges with official site links."""
    lines = [
        "**Sarvajanik University (Surat) — constituent colleges**",
        "",
        "Official university page: [sarvajanikuniversity.ac.in/aboutus](https://sarvajanikuniversity.ac.in/aboutus/)",
        "",
    ]
    resources: list[dict] = [
        {
            "type": "page",
            "url": "https://sarvajanikuniversity.ac.in/aboutus/",
            "title": "Sarvajanik University — about / constituent colleges",
            "score": 220,
            "source": "curated_portal",
            "is_portal": True,
            "curated": True,
        }
    ]
    sources: list[str] = ["https://sarvajanikuniversity.ac.in/aboutus/"]
    seen_domains: set[str] = set()
    n = 0
    for site in SU_CONSTITUENT_SITES:
        canonical = site["canonical"]
        if canonical == SU:
            continue
        urls = list(site.get("urls") or [])
        home = urls[0] if urls else f"https://www.{site['domains'][0]}/"
        # Prefer college homepage over deep pages.
        if canonical == SRKI:
            home = "https://www.srki.ac.in/"
        domain = site["domains"][0]
        if domain in seen_domains and canonical in (SCTCC, SCLA):
            # Still list them; they share SU domain.
            pass
        seen_domains.add(domain)
        n += 1
        short = {
            SRKI: "SRKI",
            SCET: "SCET",
            SCOL: "SCOL",
            BRCM: "BRCM",
            SCCCA: "SCCCA",
            SRLIM: "SRLIM",
            SCOPA: "SCOPA",
            IDPT: "IDPT",
            SCTCC: "SCTCC",
            SCLA: "SCLA",
        }.get(canonical, "")
        label = f"{n}. **{short}** — {canonical}" if short else f"{n}. **{canonical}**"
        lines.append(f"{label}")
        lines.append(f"   - Official site: [{domain}]({home})")
        resources.append(
            {
                "type": "page",
                "url": home,
                "title": f"{short or canonical} — official website",
                "score": 100 - n,
                "source": "curated",
                "curated": True,
            }
        )
        sources.append(home)
    lines.append("")
    lines.append(
        "For admissions across SU colleges, use the official admission portal: "
        "[student.sarvajanikuniversity.ac.in](https://student.sarvajanikuniversity.ac.in:8080/admissionindex.html)"
    )
    sources.append("https://student.sarvajanikuniversity.ac.in:8080/admissionindex.html")
    return "\n".join(lines), resources, list(dict.fromkeys(sources))
