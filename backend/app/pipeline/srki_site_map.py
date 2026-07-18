"""Full SRKI official website menu map + topic-aware page/PDF harvesting.

Covers Home, About Us, Academic, Departments, Campus, Students Zone, Activities,
Online Courses, Placement, Research, Ranking, Media, ICC, Sarvajanik University,
Admission Corner, Result, Examination Timetable — with sub-menu URLs from srki.ac.in.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote, urljoin

import httpx

HOME = "https://www.srki.ac.in/"

# Menu → official pages (from live homepage navigation, Jul 2026).
SRKI_MENU: dict[str, list[tuple[str, str]]] = {
    "home": [
        ("Home", HOME),
        ("Contact", "https://www.srki.ac.in/contact/"),
    ],
    "about": [
        ("SRKI — Constituent of Sarvajanik University", "https://www.srki.ac.in/pages/srki-constituent-college-of-sarvajanik-university-/"),
        ("History", "https://www.srki.ac.in/pages/history/"),
        ("Vision, Mission & Values", "https://www.srki.ac.in/pages/vision-mission-amp-values/"),
        ("Chairman's Message", "https://www.srki.ac.in/pages/chairman-s-message/"),
        ("Principal's Message", "https://www.srki.ac.in/pages/principal-s-message/"),
        ("Working Committee", "https://www.srki.ac.in/pages/working-committee/"),
        ("Donors", "https://www.srki.ac.in/pages/donors/"),
        ("Principals", "https://www.srki.ac.in/pages/principals/"),
    ],
    "academic": [
        ("AISHE", "https://www.srki.ac.in/pages/aishe/"),
        ("SU Syllabus", "https://www.srki.ac.in/pages/su-syllabus/"),
        ("Under Graduate Courses (syllabus)", "https://www.srki.ac.in/pages/under-graduate-courses/"),
        ("Post Graduate Courses (syllabus)", "https://www.srki.ac.in/pages/post-graduate-courses/"),
        ("Ph.D. Coursework Paper III & IV", "https://www.srki.ac.in/pages/phd-coursework-paper-iii-amp-iv-/"),
        ("Courses Offered", "https://www.srki.ac.in/pages/courses-offered/"),
        ("Fees Structure", "https://www.srki.ac.in/pages/fees-structure/"),
        ("Accreditation", "https://www.srki.ac.in/pages/accrediation/"),
        ("AQAR Report", "https://www.srki.ac.in/pages/aqar-report/"),
        ("IQAC Committee", "https://www.srki.ac.in/pages/iqac-committee/"),
        ("UGC Notification", "https://www.srki.ac.in/pages/ugc-notification/"),
    ],
    "department": [
        ("Computer Science", "https://www.srki.ac.in/department/computer-science/"),
        ("Microbiology", "https://www.srki.ac.in/department/microbiology/"),
        ("Biotechnology", "https://www.srki.ac.in/department/biotechnology/"),
        ("Environmental Science", "https://www.srki.ac.in/department/environmental-science/"),
        ("Chemistry", "https://www.srki.ac.in/department/chemistry/"),
        ("Allied", "https://www.srki.ac.in/department/allied/"),
        ("Admin", "https://www.srki.ac.in/department/admin/"),
        ("Library", "https://www.srki.ac.in/department/library/"),
    ],
    "campus": [
        ("NCC Office", "https://www.srki.ac.in/pages/ncc-office/"),
        ("Laboratory", "https://www.srki.ac.in/pages/laboratory/"),
        ("Library", "https://www.srki.ac.in/pages/library/"),
        ("Seminar Hall", "https://www.srki.ac.in/pages/seminar-hall/"),
        ("Playground", "https://www.srki.ac.in/pages/playground/"),
        ("Hostel", "https://www.srki.ac.in/pages/hostel/"),
        ("Canteen", "https://www.srki.ac.in/pages/canteen/"),
        ("Sports", "https://www.srki.ac.in/pages/sports/"),
    ],
    "student_zone": [
        ("Gender Sensitization Cell", "https://www.srki.ac.in/pages/gender-sensitization-cell/"),
        ("Internal Complaints Committee", "https://www.srki.ac.in/pages/internal-complaints-committee/"),
        ("Previous Question Paper", "https://www.srki.ac.in/pages/previous-question-paper/"),
        ("E-Magazine", "https://www.srki.ac.in/pages/e-magazine/"),
        ("Scholarship & Free ship", "https://www.srki.ac.in/pages/scholarship-amp-free-ship/"),
        ("Anti Ragging Committee", "https://www.srki.ac.in/pages/anti-ragging-committtee/"),
        ("Academic Calendar", "https://www.srki.ac.in/pages/academic-calender/"),
        ("Code Of Conduct", "https://www.srki.ac.in/pages/code-of-conduct/"),
        ("Forms", "https://www.srki.ac.in/pages/form/"),
        ("Lateral and Admission Form", "https://www.srki.ac.in/pages/lateral-and-admission-form/"),
        ("Application Form", "https://www.srki.ac.in/pages/application-form/"),
        ("Complaint Form", "https://www.srki.ac.in/pages/complaint-form/"),
        ("Result", "https://www.srki.ac.in/pages/result-2024-25-and-2025-26/"),
        ("Fees Payment", "https://su-fees.zeroq.net/"),
    ],
    "activities": [
        ("Cells & Committees", "https://www.srki.ac.in/pages/cells-amp-committees/"),
        ("Red Cross Activities", "https://www.srki.ac.in/pages/red-cross-activities/"),
        ("Maitri Setu", "https://www.srki.ac.in/pages/maitri-setu/"),
        ("Educational Tour", "https://www.srki.ac.in/pages/educational-tour/"),
        ("Past Activities", "https://www.srki.ac.in/pages/past-activities/"),
        ("Cultural", "https://www.srki.ac.in/pages/cultural/"),
        ("Sports Activities", "https://www.srki.ac.in/pages/sports-activities/"),
        ("NSS", "https://www.srki.ac.in/pages/nss/"),
        ("NCC", "https://www.srki.ac.in/pages/ncc/"),
    ],
    "online_courses": [
        ("IPR — Patent Searching for beginners", "https://www.srki.ac.in/pages/ipr-patent-searching-for-beginners/"),
        ("IPR — International IPR Treaties and Conventions", "https://www.srki.ac.in/pages/ipr-international-ipr-treaties-and-conventions/"),
    ],
    "placement": [
        ("Training & Placement Cell", "https://www.srki.ac.in/pages/training-amp-placement-cell/"),
        ("Events", "https://www.srki.ac.in/pages/events/"),
        ("Chemistry Placement", "https://www.srki.ac.in/pages/chemistry-placement/"),
        ("Computer Science Placement", "https://www.srki.ac.in/pages/computer-science-placement/"),
        ("Microbiology Placement", "https://www.srki.ac.in/pages/microbiology-placement/"),
        ("Biotechnology Placement", "https://www.srki.ac.in/pages/biotechnology-placement/"),
        ("Environmental Science Placement", "https://www.srki.ac.in/pages/environmental-science-placement/"),
    ],
    "research": [
        ("Research Facility", "https://www.srki.ac.in/pages/research-facility/"),
        ("Research Activities Organized", "https://www.srki.ac.in/pages/research-activities-organized/"),
        ("Paper Published by Faculties", "https://www.srki.ac.in/pages/paper-published-by-faculties/"),
        ("Research Guides", "https://www.srki.ac.in/pages/research-guides/"),
        ("Research Scholars", "https://www.srki.ac.in/pages/research-scholars/"),
    ],
    "ranking": [
        ("NIRF", "https://www.srki.ac.in/pages/nirf/"),
        ("GSIRF", "https://www.srki.ac.in/pages/gsirf/"),
    ],
    "media": [
        ("College News / Activities", "https://www.srki.ac.in/news/"),
        ("Photo Gallery / Alumni", "https://www.srki.ac.in/gallery/alumani/"),
    ],
    "icc": [
        ("About ICC", "https://www.srki.ac.in/pages/about-icc/"),
        ("Compositions/Members", "https://www.srki.ac.in/pages/compositions-members/"),
        ("Objectives-Visions", "https://www.srki.ac.in/pages/objectives-visions/"),
        ("Plan of Actions", "https://www.srki.ac.in/pages/plan-of-actions/"),
        ("Procedure for approaching committee", "https://www.srki.ac.in/pages/procedure-for-approaching-committee/"),
        ("Definition of Sexual Harassment", "https://www.srki.ac.in/pages/definition-of-sexual-harassment/"),
        ("Investigation procedure", "https://www.srki.ac.in/pages/investigation-procedure/"),
        ("Disciplinary Mechanism", "https://www.srki.ac.in/pages/disciplinary-mechanism/"),
        ("Action against frivolous complaint", "https://www.srki.ac.in/pages/action-against-frivolous-complaint/"),
    ],
    "sarvajanik_university": [
        ("Sarvajanik University", "https://sarvajanikuniversity.ac.in/"),
        ("SU Admission Portal", "https://student.sarvajanikuniversity.ac.in:8080/admissionindex.html"),
    ],
    "admission": [
        ("Admission Corner", "https://www.srki.ac.in/pages/admission-corner/"),
        ("Application Form", "https://www.srki.ac.in/pages/application-form/"),
        ("Lateral and Admission Form", "https://www.srki.ac.in/pages/lateral-and-admission-form/"),
        ("Online Admission 2020-21", "https://www.srki.ac.in/pages/online-admission-2020-21/"),
        ("Offline Admission 2020-21", "https://www.srki.ac.in/pages/offline-admission-2020-21/"),
    ],
    "result": [
        ("Result 2024-25 and 2025-26", "https://www.srki.ac.in/pages/result-2024-25-and-2025-26/"),
    ],
    "exam": [
        ("Examination Timetable", "https://www.srki.ac.in/pages/examination-time-table/"),
        ("Academic Calendar", "https://www.srki.ac.in/pages/academic-calender/"),
    ],
    "scholarship": [
        ("Scholarship & Free ship", "https://www.srki.ac.in/pages/scholarship-amp-free-ship/"),
    ],
    "fee": [
        ("Fees Structure", "https://www.srki.ac.in/pages/fees-structure/"),
        ("Fees Payment", "https://su-fees.zeroq.net/"),
        ("Fees Payment Notice", "https://www.srki.ac.in/pages/fees-payment-notice/"),
    ],
}

# Query topic → menu keys (priority order).
_TOPIC_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("scholarship", ("scholarship", "free ship", "freeship", "stipend", "financial aid", "minority scholarship")),
    ("exam", ("exam timetable", "examination timetable", "exam schedule", "time table", "timetable", "exam date", "exam dates")),
    ("result", ("result", "results", "marksheet", "marks")),
    ("placement", ("placement", "campus placement", "training and placement", "recruit")),
    ("research", ("research", "research scholar", "research guide", "publication")),
    ("ranking", ("nirf", "gsirf", "ranking", "rank")),
    ("icc", ("icc", "internal complaints", "sexual harassment", "posh")),
    ("campus", ("hostel", "canteen", "laboratory", "playground", "seminar hall", "campus")),
    ("activities", ("nss", "ncc", "cultural", "educational tour", "red cross", "maitri setu", "activities")),
    ("online_courses", ("online course", "ipr", "patent searching")),
    ("student_zone", ("previous question", "e-magazine", "anti ragging", "code of conduct", "academic calendar", "academic calender")),
    ("admission", ("admission", "apply", "eligibility", "merit list")),
    ("fee", ("fee", "fees", "tuition", "payment")),
    ("department", ("department",)),
    ("about", ("history", "vision", "mission", "principal", "chairman", "about srki", "about college")),
    ("sarvajanik_university", ("sarvajanik university", "su university")),
    ("media", ("news", "gallery", "media", "photo")),
    ("academic", ("accreditation", "aqar", "iqac", "ugc", "aishe", "courses offered")),
]


def detect_srki_topics(query: str) -> list[str]:
    low = (query or "").lower()
    topics: list[str] = []
    for topic, words in _TOPIC_PATTERNS:
        if any(w in low for w in words):
            topics.append(topic)
    return topics


def all_srki_seed_urls() -> list[str]:
    """Flat list of every mapped official URL (for deep crawl seeds)."""
    out: list[str] = [HOME]
    seen = {HOME}
    for items in SRKI_MENU.values():
        for _, url in items:
            if url.startswith("http") and url not in seen:
                seen.add(url)
                out.append(url)
    return out


def topic_portal_urls(query: str) -> list[tuple[str, str]]:
    """Return (title, url) portals for topics detected in the query."""
    topics = detect_srki_topics(query)
    if not topics:
        return [("Home", HOME)]
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for topic in topics:
        for title, url in SRKI_MENU.get(topic, []):
            if url not in seen:
                seen.add(url)
                out.append((title, url))
    return out


def _fetch_html(url: str) -> str:
    try:
        with httpx.Client(follow_redirects=True, timeout=22) as client:
            r = client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; SRKI-EduBot/1.0)"})
            r.raise_for_status()
            return r.text
    except Exception:
        return ""


def _pdfs_from_html(html: str, page_url: str, query: str) -> list[dict[str, Any]]:
    low_q = (query or "").lower()
    out: list[dict[str, Any]] = []
    for m in re.finditer(
        r'<a\b[^>]*href=["\']([^"\']+\.pdf)["\'][^>]*>(.*?)</a>',
        html,
        re.I | re.S,
    ):
        href = urljoin(page_url, m.group(1).strip())
        label = re.sub(r"<[^>]+>|&nbsp;?", " ", m.group(2)).strip()
        label = re.sub(r"\s+", " ", label)
        fname = unquote(href.rsplit("/", 1)[-1])
        if not label or label.lower().startswith("click here") or label.lower() in {"view", "download"}:
            label = fname
        else:
            label = f"{label} ({fname})"
        blob = f"{href} {label}".lower()
        score = 60
        # Prefer current year packs for exam/scholarship.
        if "2025-26" in blob or "2025" in blob:
            score += 20
        if "2024-25" in blob or "2024" in blob:
            score += 10
        for token in re.findall(r"[a-z0-9]{3,}", low_q):
            if token in blob:
                score += 4
        if any(w in low_q for w in ("regular",)) and "regular" in blob:
            score += 15
        if any(w in low_q for w in ("backlog",)) and "backlog" in blob:
            score += 15
        out.append(
            {
                "type": "pdf",
                "url": href,
                "title": label,
                "score": score,
                "source": "srki_site_map",
                "curated": True,
                "page": page_url,
            }
        )
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


def navigate_srki_topic(query: str, max_pages: int = 3, max_pdfs: int = 8) -> list[dict[str, Any]]:
    """Open topic portals from the official menu and harvest PDFs/pages."""
    portals = topic_portal_urls(query)
    if not portals:
        return []
    resources: list[dict[str, Any]] = []
    for i, (title, url) in enumerate(portals[:max_pages]):
        resources.append(
            {
                "type": "page",
                "url": url,
                "title": f"SRKI — {title}",
                "score": 220 - i,
                "source": "srki_site_map",
                "is_portal": True,
                "curated": True,
            }
        )
        html = _fetch_html(url)
        if not html:
            continue
        for pdf in _pdfs_from_html(html, url, query)[:max_pdfs]:
            pdf["title"] = f"Official — {pdf['title']}"
            resources.append(pdf)

    # Deduplicate by URL, keep highest score.
    best: dict[str, dict[str, Any]] = {}
    for r in resources:
        u = r.get("url") or ""
        if not u:
            continue
        prev = best.get(u)
        if not prev or r.get("score", 0) > prev.get("score", 0):
            best[u] = r
    return sorted(best.values(), key=lambda x: x.get("score", 0), reverse=True)
