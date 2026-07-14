"""Curated official website links when live web search is unavailable (e.g. on cloud hosts)."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from backend.app.pipeline.institution_catalog import (
    BRCM,
    GTU,
    IDPT,
    SCET,
    SCCCA,
    SCLA,
    SCOL,
    SCOPA,
    SCTCC,
    SRLIM,
    SRKI,
    SU,
    SU_CONSTITUENT_SITES,
    VNSGU,
    all_su_constituent_domains,
    get_crawl_seed_urls,
    get_extra_domains,
    is_gtu_network,
    is_su_network,
)

_SU_ADMISSION_PORTAL = "https://student.sarvajanikuniversity.ac.in:8080/admissionindex.html"
_SU_SYLLABUS_HUB = "https://www.srki.ac.in/pages/su-syllabus/"

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
        "admission": [
            "https://www.srki.ac.in/pages/admission-corner/",
            _SU_ADMISSION_PORTAL,
        ],
        "contact": [
            "https://www.srki.ac.in/contact/",
        ],
        "fee": [
            "https://www.srki.ac.in/pages/fees-structure/",
            "https://www.srki.ac.in/pages/fees-payment/",
            "https://www.srki.ac.in/pages/fees-payment-notice/",
        ],
        "fee_portal": [
            "https://www.srki.ac.in/pages/fees-structure/",
        ],
        "fee_pdfs": [
            "https://www.srki.ac.in/upload/2025-26/Fee_Batch-2026.pdf",
        ],
        "syllabus": [
            _SU_SYLLABUS_HUB,
            "https://www.srki.ac.in/pages/courses-offered/",
            "https://www.srki.ac.in/pages/srki-constituent-college-of-sarvajanik-university-/",
        ],
        "academics": [
            _SU_SYLLABUS_HUB,
            "https://www.srki.ac.in/pages/courses-offered/",
            "https://www.srki.ac.in/pages/history/",
        ],
        "form": [
            "https://www.srki.ac.in/pages/admission-corner/",
            "https://www.srki.ac.in/pages/fees-payment/",
        ],
        "syllabus_pdfs": [
            "https://www.srki.ac.in/upload/2024-25/NEP_BSc_CS_Sem1_Syllabus_CS_2024-25-1-16.pdf",
            "https://www.srki.ac.in/upload/2024-25/NEP_BSc_IT_Sem1_Syllabus_IT_2024-25.pdf",
            "https://www.srki.ac.in/upload/2022-23/B.Sc%20IT.pdf",
        ],
        "syllabus_portal": [_SU_SYLLABUS_HUB],
        "admission_portal": [
            "https://www.srki.ac.in/pages/admission-corner/",
            _SU_ADMISSION_PORTAL,
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
    SU: {
        "default": [
            "https://www.sarvajanikuniversity.ac.in/",
            "https://sarvajanikuniversity.ac.in/aboutus/",
        ],
        "syllabus": [
            _SU_SYLLABUS_HUB,
            "https://www.sarvajanikuniversity.ac.in/",
            "https://sarvajanikuniversity.ac.in/aboutus/",
        ],
        "academics": [
            "https://sarvajanikuniversity.ac.in/aboutus/",
            "https://www.srki.ac.in/pages/courses-offered/",
        ],
        "admission": [
            _SU_ADMISSION_PORTAL,
            "https://www.srki.ac.in/pages/admission-corner/",
            "https://www.sarvajanikuniversity.ac.in/",
        ],
        "contact": [
            "https://www.sarvajanikuniversity.ac.in/",
        ],
        "syllabus_portal": [
            _SU_SYLLABUS_HUB,
            "https://sarvajanikuniversity.ac.in/aboutus/",
        ],
        "admission_portal": [_SU_ADMISSION_PORTAL],
    },
    SCET: {
        "default": ["https://www.scet.ac.in/"],
        "admission": ["https://www.scet.ac.in/", _SU_ADMISSION_PORTAL],
        "syllabus": ["https://www.scet.ac.in/academics/", _SU_SYLLABUS_HUB],
        "academics": ["https://www.scet.ac.in/academics/", "https://www.scet.ac.in/"],
        "contact": ["https://www.scet.ac.in/"],
        "admission_portal": [_SU_ADMISSION_PORTAL],
        "syllabus_portal": [_SU_SYLLABUS_HUB],
    },
    SCOL: {
        "default": ["https://sarvajaniklaw.org/"],
        "admission": ["https://sarvajaniklaw.org/", _SU_ADMISSION_PORTAL],
        "syllabus": [_SU_SYLLABUS_HUB, "https://sarvajaniklaw.org/"],
        "academics": ["https://sarvajaniklaw.org/"],
        "contact": ["https://sarvajaniklaw.org/"],
        "admission_portal": [_SU_ADMISSION_PORTAL],
        "syllabus_portal": [_SU_SYLLABUS_HUB],
    },
    BRCM: {
        "default": ["https://www.brcmbba.org/"],
        "admission": ["https://www.brcmbba.org/", _SU_ADMISSION_PORTAL],
        "syllabus": ["https://www.brcmbba.org/", _SU_SYLLABUS_HUB],
        "academics": ["https://www.brcmbba.org/"],
        "contact": ["https://www.brcmbba.org/"],
        "admission_portal": [_SU_ADMISSION_PORTAL],
        "syllabus_portal": [_SU_SYLLABUS_HUB],
    },
    SCCCA: {
        "default": ["https://www.sccca.ac.in/"],
        "admission": ["https://www.sccca.ac.in/", _SU_ADMISSION_PORTAL],
        "syllabus": ["https://www.sccca.ac.in/", _SU_SYLLABUS_HUB],
        "academics": ["https://www.sccca.ac.in/"],
        "contact": ["https://www.sccca.ac.in/"],
        "admission_portal": [_SU_ADMISSION_PORTAL],
        "syllabus_portal": [_SU_SYLLABUS_HUB],
    },
    SRLIM: {
        "default": ["https://srlimba.ac.in/"],
        "admission": ["https://srlimba.ac.in/", _SU_ADMISSION_PORTAL],
        "syllabus": ["https://srlimba.ac.in/", _SU_SYLLABUS_HUB],
        "academics": ["https://srlimba.ac.in/"],
        "contact": ["https://srlimba.ac.in/"],
        "admission_portal": [_SU_ADMISSION_PORTAL],
        "syllabus_portal": [_SU_SYLLABUS_HUB],
    },
    SCOPA: {
        "default": ["https://www.scopa-surat.ac.in/"],
        "admission": ["https://www.scopa-surat.ac.in/", _SU_ADMISSION_PORTAL],
        "syllabus": ["https://www.scopa-surat.ac.in/", _SU_SYLLABUS_HUB],
        "academics": ["https://www.scopa-surat.ac.in/"],
        "contact": ["https://www.scopa-surat.ac.in/"],
        "admission_portal": [_SU_ADMISSION_PORTAL],
        "syllabus_portal": [_SU_SYLLABUS_HUB],
    },
    IDPT: {
        "default": ["https://www.idpt-scet.ac.in/"],
        "admission": ["https://www.idpt-scet.ac.in/", _SU_ADMISSION_PORTAL],
        "syllabus": ["https://www.idpt-scet.ac.in/", _SU_SYLLABUS_HUB],
        "academics": ["https://www.idpt-scet.ac.in/"],
        "contact": ["https://www.idpt-scet.ac.in/"],
        "admission_portal": [_SU_ADMISSION_PORTAL],
        "syllabus_portal": [_SU_SYLLABUS_HUB],
    },
    SCTCC: {
        "default": [
            "https://sarvajanikuniversity.ac.in/aboutus/",
            "https://www.sarvajanikuniversity.ac.in/",
        ],
        "admission": [_SU_ADMISSION_PORTAL],
        "syllabus": [_SU_SYLLABUS_HUB],
        "academics": ["https://sarvajanikuniversity.ac.in/aboutus/"],
        "admission_portal": [_SU_ADMISSION_PORTAL],
        "syllabus_portal": [_SU_SYLLABUS_HUB],
    },
    SCLA: {
        "default": [
            "https://www.sarvajanikuniversity.ac.in/pages/advertisement-sarvajanik-college-of-liberal-arts/",
            "https://sarvajanikuniversity.ac.in/aboutus/",
        ],
        "admission": [
            "https://www.sarvajanikuniversity.ac.in/pages/advertisement-sarvajanik-college-of-liberal-arts/",
            _SU_ADMISSION_PORTAL,
        ],
        "syllabus": [_SU_SYLLABUS_HUB],
        "academics": [
            "https://www.sarvajanikuniversity.ac.in/pages/advertisement-sarvajanik-college-of-liberal-arts/",
        ],
        "admission_portal": [_SU_ADMISSION_PORTAL],
        "syllabus_portal": [_SU_SYLLABUS_HUB],
    },
}

_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "admission": ("admission", "admissions", "apply", "application", "eligibility", "2026", "2025", "entrance"),
    "contact": ("contact", "address", "phone", "email", "location", "where is", "map", "directions"),
    "fee": ("fee", "fees", "tuition", "payment", "charges", "cost"),
    "form": ("form", "forms", "application form", "download form", "prospectus", "brochure"),
    "syllabus": ("syllabus", "curriculum", "semester", "scheme", "regulation", "nep"),
    "academics": ("academic", "academics", "department", "program", "programme", "faculty", "constituent colleges"),
}

# Topics where PDFs / forms / images are useful to show inline.
_MEDIA_TOPICS = frozenset({"syllabus", "admission", "fee", "form"})
_CONTACT_HINTS = ("contact", "address", "phone", "email", "location", "map", "direction")
_SYLLABUS_MEDIA_HINTS = ("syllabus", "curriculum", "scheme", "regulation", "nep", "sem")


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


def get_admission_portal_urls(institution: str, query: str = "") -> list[str]:
    catalog = INSTITUTION_OFFICIAL_LINKS.get(institution, {})
    portals = list(catalog.get("admission_portal") or [])
    if not portals and "admission" in _topics_for_query(query):
        portals = [u for u in catalog.get("admission", []) if "admission" in u.lower()]
    seen: set[str] = set()
    out: list[str] = []
    for u in portals:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def is_contact_query(query: str) -> bool:
    low = (query or "").lower()
    return any(w in low for w in _TOPIC_KEYWORDS["contact"])


def is_syllabus_topic_query(query: str) -> bool:
    if "syllabus" in _topics_for_query(query):
        return True
    low = (query or "").lower()
    if any(w in low for w in ("syllabus", "curriculum", "scheme", "regulation")):
        return True
    if re.search(r"\bsem(?:ester)?[\s\-]*\d+\b", low) and any(
        w in low for w in ("bsc", "b.sc", "m.sc", "bca", "mba", "course", "it", "cs", "subject", "nep")
    ):
        return True
    return False


def query_wants_document_media(query: str) -> bool:
    """True when the user is asking for syllabus/docs/forms that warrant PDF/image cards."""
    if is_syllabus_topic_query(query):
        return True
    topics = {t for t in _topics_for_query(query) if t != "default"}
    if topics & _MEDIA_TOPICS:
        return True
    low = (query or "").lower()
    return any(
        w in low
        for w in (
            "pdf",
            "brochure",
            "prospectus",
            "download",
            "form",
            "document",
            "image",
            "photo",
        )
    )


def get_contact_portal_urls(institution: str, query: str = "") -> list[str]:
    catalog = INSTITUTION_OFFICIAL_LINKS.get(institution, {})
    urls = list(catalog.get("contact") or [])
    if not urls:
        urls = [u for u in catalog.get("default", []) if "contact" in u.lower()]
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def is_fee_query(query: str) -> bool:
    return "fee" in _topics_for_query(query)


def get_fee_portal_urls(institution: str, query: str = "") -> list[str]:
    catalog = INSTITUTION_OFFICIAL_LINKS.get(institution, {})
    portals = list(catalog.get("fee_portal") or [])
    if not portals:
        portals = list(catalog.get("fee") or [])
    seen: set[str] = set()
    out: list[str] = []
    for u in portals:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def get_portal_page_resources(institution: str, query: str = "") -> list[dict]:
    """High-priority official portal pages for syllabus/admission/contact/fee queries."""
    topics = set(_topics_for_query(query))
    is_syllabus = "syllabus" in topics or is_syllabus_topic_query(query)
    is_admission = "admission" in topics
    is_contact = "contact" in topics
    is_fee = "fee" in topics
    if not is_syllabus and not is_admission and not is_contact and not is_fee:
        return []
    resources: list[dict] = []
    if is_fee and not is_syllabus:
        for url in get_fee_portal_urls(institution, query):
            resources.append(
                {
                    "type": "page",
                    "url": url,
                    "title": f"{institution} — official fees structure page",
                    "score": 215,
                    "source": "curated_portal",
                    "is_portal": True,
                    "curated": True,
                }
            )
    if is_contact and not is_syllabus and not is_fee:
        for url in get_contact_portal_urls(institution, query):
            resources.append(
                {
                    "type": "page",
                    "url": url,
                    "title": f"{institution} — official contact / address page",
                    "score": 210,
                    "source": "curated_portal",
                    "is_portal": True,
                    "curated": True,
                }
            )
    if is_syllabus:
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
    if is_admission and not is_contact and not is_fee:
        for url in get_admission_portal_urls(institution, query):
            resources.append(
                {
                    "type": "page",
                    "url": url,
                    "title": f"{institution} — official admission portal",
                    "score": 195,
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
    SU: tuple(sorted(all_su_constituent_domains())),
    SCET: ("scet.ac.in", "sarvajanikuniversity.ac.in", "srki.ac.in"),
    SCOL: ("sarvajaniklaw.org", "sarvajanikuniversity.ac.in", "srki.ac.in"),
    BRCM: ("brcmbba.org", "sarvajanikuniversity.ac.in", "srki.ac.in"),
    SCCCA: ("sccca.ac.in", "sarvajanikuniversity.ac.in", "srki.ac.in"),
    SRLIM: ("srlimba.ac.in", "sarvajanikuniversity.ac.in", "srki.ac.in"),
    SCOPA: ("scopa-surat.ac.in", "sarvajanikuniversity.ac.in", "srki.ac.in"),
    IDPT: ("idpt-scet.ac.in", "sarvajanikuniversity.ac.in", "srki.ac.in", "scet.ac.in"),
    SCTCC: ("sarvajanikuniversity.ac.in", "srki.ac.in"),
    SCLA: ("sarvajanikuniversity.ac.in", "srki.ac.in"),
    GTU: ("gtu.ac.in",),
    VNSGU: ("vnsgu.ac.in", "vnsguj.ac.in", "vnsguadm.samarth.edu.in", "vnsgu.net"),
    "Sardar Vallabhbhai National Institute of Technology Surat": ("svnit.ac.in",),
}

for _site in SU_CONSTITUENT_SITES:
    _canonical = _site["canonical"]
    if _canonical in _INSTITUTION_DOMAIN_HINTS:
        continue
    _INSTITUTION_DOMAIN_HINTS[_canonical] = tuple(_site["domains"])

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
    """Return curated official PDF links matching the query topic (fees / syllabus)."""
    catalog = INSTITUTION_OFFICIAL_LINKS.get(institution, {})
    low = (query or "").lower()
    out: list[dict] = []

    if is_fee_query(query):
        for url in catalog.get("fee_pdfs") or []:
            label = url.rsplit("/", 1)[-1]
            out.append(
                {
                    "type": "pdf",
                    "url": url,
                    "title": f"Official fees structure — {label}",
                    "score": 80,
                    "source": "curated",
                    "curated": True,
                }
            )
        if out:
            out.sort(key=lambda x: x["score"], reverse=True)
            return out

    if not is_syllabus_topic_query(query):
        return []
    pdfs = catalog.get("syllabus_pdfs") or []
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


def _resource_blob(resource: dict) -> str:
    return f"{resource.get('url', '')} {resource.get('title', '')} {resource.get('page_title', '')}".lower()


def _resource_topic_blob(resource: dict) -> str:
    """URL + link title only — avoids matching via the parent page title."""
    return f"{resource.get('url', '')} {resource.get('title', '')}".lower()


def filter_resources_for_query(resources: list[dict], query: str) -> list[dict]:
    """Keep only resources that help answer this query (no irrelevant PDFs/images)."""
    if not resources:
        return resources
    topics = [t for t in _topics_for_query(query) if t != "default"]
    contact_only = is_contact_query(query) and not (set(topics) & {"syllabus", "fee", "admission", "form"})
    fee_only = is_fee_query(query) and not is_syllabus_topic_query(query)
    wants_media = query_wants_document_media(query)

    out: list[dict] = []
    for r in resources:
        rtype = r.get("type") or "page"
        blob = _resource_blob(r)
        topic_blob = _resource_topic_blob(r)
        if r.get("is_portal") or r.get("source") == "curated_portal":
            out.append(r)
            continue

        if contact_only:
            if rtype in ("pdf", "document", "image"):
                if any(h in topic_blob for h in _CONTACT_HINTS):
                    out.append(r)
                continue
            if any(h in topic_blob for h in _CONTACT_HINTS):
                out.append(r)
            continue

        if fee_only:
            fee_hints = ("fee", "fees", "tuition", "payment", "batch-2026", "fee_batch", "fee_202")
            if rtype in ("pdf", "document"):
                if any(h in topic_blob for h in fee_hints) or r.get("curated"):
                    out.append(r)
                continue
            if rtype == "image":
                if any(h in topic_blob for h in fee_hints):
                    out.append(r)
                continue
            if rtype == "page" and any(h in topic_blob for h in fee_hints):
                out.append(r)
            continue

        if not wants_media and rtype in ("pdf", "document", "image"):
            continue

        if rtype == "pdf" and wants_media:
            if is_syllabus_topic_query(query):
                if any(h in blob for h in _SYLLABUS_MEDIA_HINTS) or r.get("curated") or r.get("has_content"):
                    out.append(r)
                continue
            out.append(r)
            continue

        if rtype == "image":
            if any(h in topic_blob for h in ("map", "campus", "brochure", "prospectus", "fee", "form", "admission")):
                out.append(r)
            continue

        out.append(r)

    if contact_only:
        contact_pages = [
            r for r in out if any(h in _resource_topic_blob(r) for h in _CONTACT_HINTS) or r.get("is_portal")
        ]
        if contact_pages:
            ordered = [r for r in out if r.get("is_portal")] + [
                r for r in contact_pages if not r.get("is_portal")
            ]
            return list({r.get("url"): r for r in ordered}.values())

    if fee_only:
        fee_hints = ("fee", "fees", "tuition", "payment", "batch-2026", "fee_batch", "fee_202")
        fee_items = [
            r
            for r in out
            if r.get("is_portal")
            or any(h in _resource_topic_blob(r) for h in fee_hints)
            or (r.get("type") == "pdf" and r.get("curated"))
        ]
        if fee_items:
            # Prefer newest fee PDF; drop older fee images/PDFs when a current PDF exists.
            current = [
                r
                for r in fee_items
                if r.get("type") == "pdf"
                and any(y in _resource_topic_blob(r) for y in ("2025-26", "2026", "batch-2026"))
            ]
            if current:
                fee_items = [
                    r
                    for r in fee_items
                    if r.get("is_portal")
                    or r.get("type") == "page"
                    or r in current
                    or (r.get("type") == "pdf" and r.get("curated") and r in current)
                ]
                # Keep portal + current PDFs only (no stale fee images).
                fee_items = [
                    r
                    for r in fee_items
                    if r.get("is_portal") or r.get("type") == "page" or r.get("type") == "pdf"
                ]
            fee_items.sort(
                key=lambda r: (
                    0 if r.get("is_portal") else 1,
                    0 if "2025-26" in _resource_topic_blob(r) or "2026" in _resource_topic_blob(r) else 1,
                    0 if r.get("type") == "pdf" else 2,
                    -(r.get("score") or 0),
                )
            )
            return list({r.get("url"): r for r in fee_items}.values())

    return out
