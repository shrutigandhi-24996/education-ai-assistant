"""Curated official website links when live web search is unavailable (e.g. on cloud hosts)."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

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
    get_srki_department_urls_for_query,
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
            "https://www.srki.ac.in/pages/application-form/",
            "https://www.srki.ac.in/pages/lateral-and-admission-form/",
            _SU_ADMISSION_PORTAL,
        ],
        "admission_pdfs": [
            "https://www.srki.ac.in/upload/files/admission%20form.pdf",
            "https://www.srki.ac.in/upload/2025-26/Lateral%20and%20Transfer%20Admission%20Form.pdf",
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
        # Official syllabus PDFs harvested from SRKI department pages (2023-24 NEP + older semesters).
        "syllabus_pdfs": [
            # Microbiology / Biotech / Chemistry shared Sem-1 (user-verified official link)
            "https://www.srki.ac.in/upload/2023-24/syllabus/bt-ch-mb-sem1-merged.pdf",
            "https://www.srki.ac.in/upload/2023-24/syllabus/NEP%202024%20MB%20COMPLETE.pdf",
            "https://www.srki.ac.in/upload/2023-24/syllabus/NEP%202024%20BT%20COMPLETE.pdf",
            "https://www.srki.ac.in/upload/2023-24/syllabus/NEP%202024%20CHE%20COMPLETE.pdf",
            "https://www.srki.ac.in/upload/2023-24/syllabus/NEP%202024%20ES%20COMPLETE.pdf",
            # B.Sc. Environmental Science — from official UG syllabus page tabs
            "https://www.srki.ac.in/upload/2025-26/Es-syll-2122/Curriculum-ENVIRONMENTAL%20SCIENCE%20(B-Sc-ES%20)%202021-22-1-18.pdf",
            "https://www.srki.ac.in/upload/2025-26/Es-syll-2122/Curriculum-ENVIRONMENTAL%20SCIENCE%20(B-Sc-ES%20)%202021-22-19-26.pdf",
            "https://www.srki.ac.in/upload/2025-26/Es-syll-2122/Curriculum-ENVIRONMENTAL%20SCIENCE%20(B-Sc-ES%20)%202021-22-27-35.pdf",
            "https://www.srki.ac.in/upload/2025-26/Es-syll-2122/Curriculum-ENVIRONMENTAL%20SCIENCE%20(B-Sc-ES%20)%202021-22-36-45.pdf",
            "https://www.srki.ac.in/upload/2025-26/Es-syll-2122/Curriculum-ENVIRONMENTAL%20SCIENCE%20(B-Sc-ES%20)%202021-22-46-55.pdf",
            "https://www.srki.ac.in/upload/2025-26/Es-syll-2122/Curriculum-ENVIRONMENTAL%20SCIENCE%20(B-Sc-ES%20)%202021-22-56-67.pdf",
            "https://www.srki.ac.in/upload/2025-26/B-Sc-ES%20(Hons-)%20Sem-3_Major.pdf",
            "https://www.srki.ac.in/upload/2025-26/B-Sc-BT-CH-ES-MB%20(Hons-)%20Sem-5_6.pdf",
            "https://www.srki.ac.in/upload/2021-22/b.sc.%20biotechnology%20sem-1.pdf",
            "https://www.srki.ac.in/upload/2025-26/M-Sc%20ES_Sem1.pdf",
            "https://www.srki.ac.in/upload/2025-26/M-Sc%20ES_Sem2.pdf",
            # Computer Science / IT / AIDS
            "https://www.srki.ac.in/upload/2024-25/NEP_BSc_CS_Sem1_Syllabus_CS_2024-25-1-16.pdf",
            "https://www.srki.ac.in/upload/2024-25/NEP_BSc_IT_Sem1_Syllabus_IT_2024-25.pdf",
            "https://www.srki.ac.in/upload/2023-24/syllabus/cs-sem-1.pdf",
            "https://www.srki.ac.in/upload/2023-24/syllabus/bsccs_2023_nep_16-06-23.pdf",
            "https://www.srki.ac.in/upload/2023-24/syllabus/BScAIDS_Sem-1.pdf",
            "https://www.srki.ac.in/upload/2021-22/bsc_cs_sem-2.pdf",
            "https://www.srki.ac.in/upload/2021-22/bsc_cs_sem-3.pdf",
            "https://www.srki.ac.in/upload/2021-22/bsc_cs_sem-4.pdf",
            "https://www.srki.ac.in/upload/2021-22/bsc_cs_sem-5.pdf",
            "https://www.srki.ac.in/upload/2021-22/bsc_cs_sem-6.pdf",
            # Microbiology older semester PDFs
            "https://www.srki.ac.in/upload/2021-22/b.sc.%20mb%20sem%202.pdf",
            "https://www.srki.ac.in/upload/2021-22/b.sc.%20mb%20sem%203.pdf",
            "https://www.srki.ac.in/upload/2021-22/b.sc.%20mb%20sem%204.pdf",
            "https://www.srki.ac.in/upload/2021-22/b.sc.%20mb%20sem%205.pdf",
            "https://www.srki.ac.in/upload/2021-22/b.sc.%20mb%20sem%206.pdf",
            "https://www.srki.ac.in/upload/2021-22/m.sc.%20mb%20sem%201.pdf",
            "https://www.srki.ac.in/upload/2021-22/m.sc.%20mb%20sem%202.pdf",
            # Biotechnology older semester PDFs
            "https://www.srki.ac.in/upload/2021-22/b.sc.%20biotech%20sem%202.pdf",
            "https://www.srki.ac.in/upload/2021-22/b.sc.%20biotech%20sem%203.pdf",
            "https://www.srki.ac.in/upload/2021-22/b.sc.%20bt-sem-2.pdf",
            "https://www.srki.ac.in/upload/2022-23/m.sc.%20biotechnology%20sem-1%20(1).pdf",
            # Environmental Science
            "https://www.srki.ac.in/upload/2021-22/b.sc.%20es%20sem%202.pdf",
            "https://www.srki.ac.in/upload/2021-22/b.sc.%20es%20sem%203.pdf",
            "https://www.srki.ac.in/upload/2022-23/m%20sc%20es%20sem%201.pdf",
            # Chemistry
            "https://www.srki.ac.in/upload/2021-22/b.sc.%20chemistry%20sem.-ii.pdf",
            "https://www.srki.ac.in/upload/2021-22/m.sc.%20organic%20chemistry%20semester%20-%20i_1.pdf",
            # M.Sc. IT / MCT
            "https://www.srki.ac.in/upload/2021-22/msc_it_sem-1-1-6.pdf",
            "https://www.srki.ac.in/upload/2021-22/msc_it_sem-2.pdf",
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
_FEE_MEDIA_HINTS = (
    "fee", "fees", "tuition", "payment", "batch-2026", "fee_batch", "fee_202",
    "fees-structure", "fees-payment",
)
_ADMISSION_MEDIA_HINTS = (
    "admission", "admissions", "apply", "application", "eligibility", "merit",
    "prospectus", "brochure", "admission-corner", "entrance",
)
# Per-topic hints used when a query asks for SEVERAL topics at once (multi-intent).
_TOPIC_MEDIA_HINTS: dict[str, tuple[str, ...]] = {
    "fee": _FEE_MEDIA_HINTS,
    "admission": _ADMISSION_MEDIA_HINTS,
    "syllabus": _SYLLABUS_MEDIA_HINTS,
    "contact": _CONTACT_HINTS,
    "form": ("form", "application", "prospectus", "brochure", "download"),
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
    # SRKI official menu: Academic → SU Syllabus → UG / PG / PhD.
    if institution == SRKI:
        from backend.app.pipeline.srki_syllabus_nav import (
            PG_SYLLABUS_PAGE,
            PHD_SYLLABUS_PAGE,
            SU_SYLLABUS_HUB,
            UG_SYLLABUS_PAGE,
            detect_level_from_query,
        )

        level = detect_level_from_query(query)
        portals = [SU_SYLLABUS_HUB] + portals
        if level == "pg":
            portals.insert(1, PG_SYLLABUS_PAGE)
        elif level == "phd":
            portals.insert(1, PHD_SYLLABUS_PAGE)
        else:
            portals.insert(1, UG_SYLLABUS_PAGE)
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


def is_admission_query(query: str) -> bool:
    return "admission" in _topics_for_query(query)


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
        # SRKI department pages host the actual semester syllabus PDFs.
        if institution == SRKI:
            for dept_url in get_srki_department_urls_for_query(query):
                dept_name = dept_url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
                resources.append(
                    {
                        "type": "page",
                        "url": dept_url,
                        "title": f"SRKI — {dept_name} department (official syllabus PDFs)",
                        "score": 205,
                        "source": "curated_portal",
                        "is_portal": True,
                        "curated": True,
                    }
                )
    # Multi-intent (e.g. "admission process and fees"): show the admission portal
    # card alongside the fee card instead of dropping it.
    if is_admission and not is_contact:
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
    """Return curated official PDF links matching the query topic (fees / admission / syllabus)."""
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

    if is_admission_query(query):
        for url in catalog.get("admission_pdfs") or []:
            label = unquote(url.rsplit("/", 1)[-1])
            out.append(
                {
                    "type": "pdf",
                    "url": url,
                    "title": f"Official admission form — {label}",
                    "score": 70,
                    "source": "curated",
                    "curated": True,
                }
            )

    if not is_syllabus_topic_query(query):
        out.sort(key=lambda x: x["score"], reverse=True)
        return out
    pdfs = catalog.get("syllabus_pdfs") or []
    for url in pdfs:
        label = unquote(url.rsplit("/", 1)[-1])
        score = _score_syllabus_pdf(low, label, url)
        if score < 15:
            continue
        out.append(
            {
                "type": "pdf",
                "url": url,
                "title": f"Official syllabus — {label}",
                "score": score,
                "source": "curated",
                "curated": True,
            }
        )
    out.sort(key=lambda x: x["score"], reverse=True)
    if out:
        # Keep only strong matches near the best score (avoid mixing B.Sc./M.Sc. or wrong semesters).
        best = out[0]["score"]
        out = [r for r in out if r["score"] >= max(best - 50, 80)] or out[:1]
    return out[:3]


def _score_syllabus_pdf(query_low: str, label: str, url: str = "") -> int:
    """Rank an official syllabus PDF against the user's course + semester request."""
    label_l = unquote(label).lower().replace("%20", " ")
    blob = f"{label_l} {unquote(url).lower()}"
    score = 20

    # --- Semester match ---
    sem_req = None
    for n in range(1, 9):
        if re.search(rf"\bsem(?:ester)?[\s\-]*{n}\b", query_low):
            sem_req = n
            break
    if sem_req is not None:
        if re.search(rf"\bsem(?:ester)?[\s\.\-]*{sem_req}\b|sem{sem_req}\b|sem_{sem_req}\b|-{sem_req}\.pdf", blob):
            score += 45
        elif re.search(r"\bsem(?:ester)?[\s\.\-]*[1-8]\b", blob) or re.search(r"sem[1-8]\b", blob):
            # Wrong semester in filename — demote strongly.
            score -= 50
        # Complete/merged NEP packs still useful when semester is requested.
        if "complete" in blob or "merged" in blob:
            if sem_req == 1 and ("sem1" in blob or "sem-1" in blob or "sem 1" in blob or "merged" in blob):
                score += 20
            elif "complete" in blob:
                score += 8

    # --- Course / programme match ---
    course_boosts: list[tuple[tuple[str, ...], tuple[str, ...], int]] = [
        (("microbiology", " mb ", " mb%", "/mb%", "b.sc. mb", "b sc mb"), ("mb", "microbiology", "bt-ch-mb"), 55),
        (("biotechnology", " biotech", " bt ", "b.sc. bt", "b sc bt"), ("bt", "biotech", "biotechnology", "bt-ch-mb"), 55),
        (("chemistry", " che ", "organic chemistry"), ("che", "chemistry", "organic", "bt-ch-mb", "ch-mb"), 55),
        (
            ("environmental", " env ", " es ", "bsc es", "b.sc es", "b.sc. es"),
            ("es-syll", "b-sc-es", "b.sc-es", "environmental science", "environmental", "m-sc es", "m-sc%20es"),
            55,
        ),
        (("information technology", " bsc it", "b.sc it", " bsc_it"), ("_it_", "bsc_it", "it_202", "b.sc it", "b.sc%20it", "msc_it"), 55),
        (("computer science", " bsc cs", "b.sc cs", "computer"), ("_cs_", "bsccs", "cs-sem", "computer", "bsc_cs"), 55),
        (("aids", "artificial intelligence", "data science"), ("aids", "data", "ai"), 55),
        (("mobile and cloud", "mct", "wmt"), ("mct", "wmt", "mobile"), 40),
        (("pgdmlt", "medical laboratory"), ("pgdmlt", "mlt"), 40),
    ]
    matched_course = False
    for q_hints, file_hints, boost in course_boosts:
        if any(h.strip() in query_low for h in q_hints):
            if any(h in blob for h in file_hints):
                score += boost
                matched_course = True
            else:
                score -= 35

    # Degree level (strict — do not mix B.Sc. and M.Sc. PDFs)
    wants_msc = bool(re.search(r"\bm\.?\s*sc\.?\b|\bmsc\b", query_low))
    wants_bsc = bool(re.search(r"\bb\.?\s*sc\.?\b|\bbsc\b", query_low))
    file_is_msc = bool(re.search(r"\bm\.?\s*sc\.?\b|\bmsc[_\s\-]|\bm%20sc", blob))
    file_is_bsc = bool(re.search(r"\bb\.?\s*sc\.?\b|\bbsc[_\s\-]|bt-ch-mb|bsccs|bscaids", blob))
    if wants_msc and not wants_bsc:
        if file_is_msc:
            score += 18
        if file_is_bsc and not file_is_msc:
            score -= 60
    if wants_bsc and not wants_msc:
        if file_is_bsc or "bt-ch-mb" in blob or "nep 2024 mb" in blob or "nep 2024 bt" in blob:
            score += 18
        if file_is_msc and not file_is_bsc:
            score -= 60

    # Recency
    if "2024-25" in blob or "2024" in blob or "nep 2024" in blob:
        score += 8
    if "2023-24" in blob or "2023" in blob:
        score += 6
    if "2021-22" in blob:
        score -= 4

    # Prefer syllabus-folder / NEP packs over activity reports that slipped in.
    if "/syllabus/" in blob or "syllabus" in blob or "nep" in blob or "complete" in blob:
        score += 10
    if "report" in blob or "visit" in blob or "celebration" in blob:
        score -= 40

    if not matched_course and any(
        w in query_low
        for w in (
            "microbiology", "biotechnology", "chemistry", "environmental",
            "computer science", "information technology", "aids",
        )
    ):
        # Query named a course but this PDF doesn't match — keep score low.
        score = min(score, 10)

    return score


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


def _topic_blob_has_hint(blob: str, hints: tuple[str, ...] | list[str]) -> bool:
    """Match topic hints as whole path/title tokens, not substrings (e.g. fee ≠ Feedback)."""
    low = (blob or "").lower()
    for h in hints:
        if not h:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(h.lower())}(?![a-z0-9])", low):
            return True
    return False


def filter_resources_for_query(resources: list[dict], query: str) -> list[dict]:
    """Keep only resources that help answer this query (no irrelevant PDFs/images)."""
    if not resources:
        return resources
    topics = [t for t in _topics_for_query(query) if t != "default"]
    core_topics = set(topics) & set(_TOPIC_MEDIA_HINTS)

    # Multi-intent query (e.g. "admission process and fees structure"): keep
    # resources relevant to ANY requested topic so every intent gets its media.
    if len(core_topics) >= 2:
        hints = tuple(h for t in core_topics for h in _TOPIC_MEDIA_HINTS[t])
        stale_years = ("2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25")
        multi_out: list[dict] = []
        for r in resources:
            rtype = r.get("type") or "page"
            blob = _resource_topic_blob(r)
            if any(y in blob for y in stale_years) and not r.get("is_portal"):
                continue
            if r.get("is_portal") or r.get("source") == "curated_portal" or r.get("curated"):
                multi_out.append(r)
                continue
            if _topic_blob_has_hint(blob, hints):
                multi_out.append(r)
                continue
            if rtype == "page":
                multi_out.append(r)
        return list({r.get("url"): r for r in multi_out}.values())

    contact_only = is_contact_query(query) and not (set(topics) & {"syllabus", "fee", "admission", "form"})
    fee_only = is_fee_query(query) and not is_syllabus_topic_query(query)
    syllabus_only = is_syllabus_topic_query(query) and not fee_only
    wants_media = query_wants_document_media(query)
    low = (query or "").lower()

    out: list[dict] = []
    for r in resources:
        rtype = r.get("type") or "page"
        topic_blob = _resource_topic_blob(r)
        if r.get("is_portal") or r.get("source") == "curated_portal":
            out.append(r)
            continue

        if contact_only:
            if rtype in ("pdf", "document", "image"):
                if _topic_blob_has_hint(topic_blob, _CONTACT_HINTS):
                    out.append(r)
                continue
            if _topic_blob_has_hint(topic_blob, _CONTACT_HINTS):
                out.append(r)
            continue

        if fee_only:
            fee_hints = ("fee", "fees", "tuition", "payment", "batch-2026", "fee_batch", "fee_202", "fees-structure", "fees-payment")
            if rtype in ("pdf", "document"):
                if _topic_blob_has_hint(topic_blob, fee_hints) or r.get("curated"):
                    out.append(r)
                continue
            if rtype == "image":
                if _topic_blob_has_hint(topic_blob, fee_hints):
                    out.append(r)
                continue
            if rtype == "page" and _topic_blob_has_hint(topic_blob, fee_hints):
                out.append(r)
            continue

        if syllabus_only:
            # Only syllabus portal + syllabus PDFs — no committees, webinars, gallery, fees.
            if rtype == "pdf":
                if (
                    _topic_blob_has_hint(topic_blob, _SYLLABUS_MEDIA_HINTS)
                    or r.get("curated")
                    or "syllabus" in topic_blob
                ):
                    if _topic_blob_has_hint(topic_blob, ("fee", "fees", "tuition", "payment", "merit", "brochure")):
                        continue
                    out.append(r)
                continue
            if rtype == "page" and _topic_blob_has_hint(
                topic_blob, ("syllabus", "curriculum", "scheme", "courses-offered", "su-syllabus")
            ):
                out.append(r)
            continue

        if not wants_media and rtype in ("pdf", "document", "image"):
            continue

        if rtype == "pdf" and wants_media:
            out.append(r)
            continue

        if rtype == "image":
            if _topic_blob_has_hint(
                topic_blob, ("map", "campus", "brochure", "prospectus", "fee", "fees", "form", "admission")
            ):
                out.append(r)
            continue

        out.append(r)

    if contact_only:
        contact_pages = [
            r
            for r in out
            if _topic_blob_has_hint(_resource_topic_blob(r), _CONTACT_HINTS) or r.get("is_portal")
        ]
        if contact_pages:
            ordered = [r for r in out if r.get("is_portal")] + [
                r for r in contact_pages if not r.get("is_portal")
            ]
            return list({r.get("url"): r for r in ordered}.values())

    if fee_only:
        fee_hints = ("fee", "fees", "tuition", "payment", "batch-2026", "fee_batch", "fee_202", "fees-structure", "fees-payment")
        fee_items = [
            r
            for r in out
            if r.get("is_portal")
            or _topic_blob_has_hint(_resource_topic_blob(r), fee_hints)
            or (r.get("type") == "pdf" and r.get("curated"))
        ]
        if fee_items:
            current = [
                r
                for r in fee_items
                if r.get("type") == "pdf"
                and any(y in _resource_topic_blob(r) for y in ("2025-26", "2026", "batch-2026"))
            ]
            if current:
                # Keep portal + fee-topic pages + current fee PDF only.
                fee_items = [
                    r
                    for r in fee_items
                    if r.get("is_portal")
                    or r in current
                    or (
                        r.get("type") == "page"
                        and _topic_blob_has_hint(_resource_topic_blob(r), fee_hints)
                    )
                ]
            fee_items.sort(
                key=lambda r: (
                    0 if r.get("is_portal") else 1,
                    0 if "2025-26" in _resource_topic_blob(r) or "2026" in _resource_topic_blob(r) else 1,
                    0 if r.get("type") == "pdf" else 2,
                    -(r.get("score") or 0),
                )
            )
            return list({r.get("url"): r for r in fee_items}.values())[:4]

    if syllabus_only:
        pdfs = [r for r in out if r.get("type") == "pdf"]
        portals = [r for r in out if r.get("is_portal") or r.get("source") == "curated_portal"]
        pages = [
            r
            for r in out
            if r.get("type") == "page"
            and not r.get("is_portal")
            and _topic_blob_has_hint(_resource_topic_blob(r), ("syllabus", "curriculum", "su-syllabus"))
        ]

        def _pdf_rank(r: dict) -> tuple:
            b = _resource_topic_blob(r)
            score = r.get("score") or 0
            if r.get("curated"):
                score += 20
            if "it" in low.split() or "information technology" in low:
                if "_it_" in b or "bsc_it" in b or "b.sc%20it" in b or "it_202" in b:
                    score += 50
                if ("_cs_" in b or "bsccs" in b) and "_it_" not in b:
                    score -= 40
            if "cs" in low.split() or "computer science" in low:
                if "_cs_" in b or "bsccs" in b or ("computer" in b and "science" in b):
                    score += 50
                if "_it_" in b and "_cs_" not in b:
                    score -= 40
            # Strong semester preference.
            wants_sem1 = any(x in low for x in ("sem1", "sem 1", "sem-1", "semester 1", "semester-1"))
            wants_sem2 = any(x in low for x in ("sem2", "sem 2", "sem-2", "semester 2", "semester-2"))
            if wants_sem1:
                if any(x in b for x in ("sem1", "sem-1", "sem_1", "1-16", "sem%201")):
                    score += 60
                if any(x in b for x in ("sem2", "sem-2", "sem_2", "17-29", "semester-ii", "semester ii")):
                    score -= 80
            if wants_sem2:
                if any(x in b for x in ("sem2", "sem-2", "sem_2", "17-29")):
                    score += 60
                if any(x in b for x in ("sem1", "sem-1", "sem_1", "1-16")):
                    score -= 80
            return (-score,)

        pdfs.sort(key=_pdf_rank)
        keep = portals + pdfs[:2] + pages[:1]
        return list({r.get("url"): r for r in keep}.values())

    return out


def filter_sources_for_query(
    sources: list[str],
    query: str,
    resources: list[dict] | None = None,
) -> list[str]:
    """Limit source pills to URLs that actually answer this query."""
    if not sources:
        return sources
    resources = resources or []
    keep: list[str] = []
    seen: set[str] = set()

    for r in resources:
        u = r.get("url") or ""
        if u and u not in seen:
            seen.add(u)
            keep.append(u)

    topics = [t for t in _topics_for_query(query) if t != "default"]
    topic_hints: list[str] = []
    if "contact" in topics:
        topic_hints.extend(["contact", "address"])
    if "fee" in topics:
        topic_hints.extend(["fee", "fees", "payment"])
    if "syllabus" in topics or is_syllabus_topic_query(query):
        topic_hints.extend(["syllabus", "curriculum", "scheme"])
    if "admission" in topics:
        topic_hints.extend(["admission"])

    for u in sources:
        if u in seen:
            continue
        low = u.lower()
        if topic_hints and any(h in low for h in topic_hints):
            seen.add(u)
            keep.append(u)

    # Cap noise in the UI.
    if is_contact_query(query) or is_fee_query(query) or is_syllabus_topic_query(query):
        return keep[:5]
    return keep[:8]
