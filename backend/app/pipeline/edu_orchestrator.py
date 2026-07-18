"""General Education-domain assistant orchestrator (LLM brain + web grounding).

Flow (matches the hybrid diagrams, generalised beyond SRKI):
  preprocess -> LLM analyze (domain guard + intent/multi-intent + role/multi-user
  + pragmatic context) -> web search grounding (for specific facts) -> LLM
  generate grounded answer with cited sources.

Not dependent on any local dataset: knowledge comes from the LLM + live web
search. Works for any college/university, scholarships, departments, faculty,
career guidance, etc.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from backend.app.config import settings
from backend.app.disambiguation import (
    apply_resolutions,
    find_ambiguous_terms,
    format_clarification,
    reconcile_resolutions,
    resolve_from_reply,
)
from backend.app.pipeline.clarification_ui import build_clarification_options
from backend.app.pipeline.institution_disambiguation import (
    detect_institution,
    expand_institution_aliases,
    find_ambiguous_institutions,
    format_institution_clarification,
    resolve_from_history,
    resolve_institution_from_reply,
)
from backend.app.pipeline.institution_catalog import (
    GTU,
    PARENT_UNIVERSITY,
    SRKI,
    SU,
    format_srki_courses_answer,
    format_su_constituent_colleges_answer,
    get_asset_harvest_pages,
    get_constituent_primary_domain,
    get_crawl_seed_urls,
    get_parent_university,
    get_srki_department_urls_for_query,
    is_constituent_list_query,
    is_courses_offered_query,
    is_gtu_network,
    is_srki_only,
    is_su_network,
    is_vnsgu_network,
    resolve_bare_su,
    resolve_constituent,
)
from backend.app.pipeline.institution_web_resolver import (
    find_unknown_institution_tokens,
    format_web_institution_clarification,
    search_institution_by_short_name,
)
from backend.app.pipeline.local_dataset import try_local_curriculum_block
from backend.app.pipeline.llm_client import LLMClient
from backend.app.pipeline.official_links import (
    filter_resources_for_institution,
    filter_resources_for_query,
    filter_sources_for_query,
    filter_urls_for_institution,
    get_curated_pdf_results,
    get_fee_portal_urls,
    get_institution_domains,
    get_official_search_results,
    get_official_urls,
    get_portal_page_resources,
    get_syllabus_portal_urls,
    is_admission_query,
    is_contact_query,
    is_fee_query,
    is_junk_pdf,
    query_wants_document_media,
    url_belongs_to_institution,
)
from backend.app.pipeline.page_assets import _asset_type, harvest_official_assets
from backend.app.pipeline.pdf_reader import enrich_pdf_resources, format_pdf_context_blocks
from backend.app.pipeline.preprocessing import preprocess
from backend.app.pipeline.site_navigator import crawl_official_site, is_syllabus_query
from backend.app.pipeline.srki_site_map import detect_srki_topics, navigate_srki_topic
from backend.app.pipeline.srki_syllabus_nav import (
    expand_course_short_names,
    format_course_resolution_note,
    navigate_srki_syllabus,
)
from backend.app.pipeline.web_search import (
    fetch_page_extract,
    find_official_urls_for_institution,
    search_many_parallel,
)

# Any of these signals means the answer needs LIVE, source-cited facts
# (a specific institution anywhere in the world, or a factual lookup).
_INSTITUTION_WORDS = (
    "university",
    "college",
    "school",
    "institute",
    "institution",
    "campus",
    "polytechnic",
    "academy",
    "vidyalaya",
    "vishwavidyalaya",
    "iit",
    "nit",
    "iiit",
    "iim",
    "aiims",
    "vnsgu",
)
_FACTUAL_WORDS = (
    "admission",
    "apply",
    "eligibility",
    "fee",
    "fees",
    "tuition",
    "deadline",
    "last date",
    "cutoff",
    "cut off",
    "scholarship",
    "ranking",
    "rank",
    "placement",
    "course",
    "courses",
    "program",
    "programme",
    "department",
    "faculty",
    "contact",
    "website",
    "address",
    "result",
    "exam",
    "syllabus",
)

# Comparative / general queries — no single named institution required.
_GENERAL_QUERY_PATTERNS = (
    r"\btop\s+\d*\s*(universities|colleges|schools)\b",
    r"\bbest\s+(universities|colleges|schools)\b",
    r"\bhow\s+(do|to)\s+(i|you)\s+become\b",
    r"\bdifference\s+between\b",
    r"\bcompare\b",
    r"\bin\s+general\b",
    r"\bwhich\s+(university|college|school)\s+is\s+best\b",
)

# Official / authoritative domains to surface first.
_OFFICIAL_DOMAIN = re.compile(
    r"(\.edu|\.gov|\.ac\.[a-z]{2,3}|\.edu\.[a-z]{2,3}|\.gov\.[a-z]{2,3}|"
    r"\.ac\.in|\.edu\.in|\.nic\.in|\.res\.in)$"
)

OFF_TOPIC_REPLY = (
    "I'm the **SRKI Educational Chatbot** — I answer education-related questions about "
    "**Shree Ramkrishna Institute of Computer Education and Applied Sciences (SRKI), Surat**: "
    "admissions, courses, syllabus, fees, departments, exams, contact details, and campus information.\n\n"
    "Your question seems outside the education domain, so I can't help with it.\n\n"
    "Please ask me something about SRKI — for example admissions, fees structure, "
    "BSc/MSc courses, syllabus, or contact details — and I'll answer from official sources."
)

SRKI_SCOPE_REPLY = (
    "Right now I answer questions about **Shree Ramkrishna Institute of Computer Education and "
    "Applied Sciences (SRKI), Surat** only.\n\n"
    "I can help you with SRKI's:\n"
    "- Admissions & eligibility\n"
    "- Courses (BSc/MSc — Computer Science, IT, Microbiology, Biotechnology, Chemistry & more)\n"
    "- Syllabus (semester-wise official PDFs)\n"
    "- Fees structure & payment\n"
    "- Departments, exams, results & contact details\n\n"
    "Official website: [srki.ac.in](https://www.srki.ac.in/)\n\n"
    "Please ask your question about **SRKI** and I'll answer from official sources."
)

GREETING_REPLY = """Hello! Welcome to the **SRKI Educational Chatbot**.

I answer questions about **Shree Ramkrishna Institute of Computer Education and Applied Sciences (SRKI), Surat** — a constituent college of Sarvajanik University.

I can help you with:

- **Admissions** — process, eligibility, application forms
- **Courses** — BSc/MSc in Computer Science, IT, Microbiology, Biotechnology, Chemistry & more
- **Syllabus** — official semester-wise syllabus PDFs
- **Fees** — programme-wise fees structure & payment
- **Departments, exams, results & contact details**

All answers come from SRKI's official website with verified links and documents.

What would you like to know about SRKI?"""

GREETING_REPLY_GENERAL = """Hello! Welcome to the **Innovative Educational Chatbot**.

I'm here to help students, parents, and educators with:

- Admissions, fees, scholarships & eligibility (any college/university/school worldwide)
- Courses, departments, faculty & exam schedules
- Career guidance in education
- Official website links and up-to-date information from the web

Ask me anything about education — you can use short names like **VNSGU**, **IIT**, **MIT**, etc.
If you don't mention a university/college/school, I'll ask which one you mean so I can give **official links**.
If an abbreviation is ambiguous, I'll ask you to pick the correct option.

How can I help you today?"""

NOT_CONFIGURED_REPLY = (
    "The AI brain isn't configured yet. Add a Groq API key to `.env` "
    "(`GROQ_API_KEY=gsk_...`) and restart the server."
)


class EduSession:
    def __init__(self) -> None:
        self.history: list[dict[str, str]] = []
        self.resolved_entities: dict[str, str] = {}
        self.pending_institution: dict[str, list[dict[str, str]]] = {}
        self.pending_course: dict[str, list[dict[str, str]]] = {}
        self.pending_query: str | None = None
        self.pending_institution_name: bool = False
        self.pending_institution_query: str | None = None
        self.pending_web_institution: dict[str, Any] = {}
        self.last_institution: str | None = None


class EduOrchestrator:
    def __init__(self) -> None:
        self.llm = LLMClient()
        self.sessions: dict[str, EduSession] = {}

    @property
    def ready(self) -> bool:
        return self.llm.ready

    def get_session(self, session_id: str) -> EduSession:
        if session_id not in self.sessions:
            self.sessions[session_id] = EduSession()
        return self.sessions[session_id]

    @staticmethod
    def _is_greeting(text: str) -> bool:
        t = text.lower().strip(" .!?")
        if t in {
            "hello", "hi", "hey", "hello..", "hii", "hiii",
            "good morning", "good afternoon", "good evening",
            "namaste", "howdy",
        }:
            return True
        return t.startswith(("hello ", "hi ", "hey ", "good morning", "good afternoon"))

    @staticmethod
    def _is_official(url: str) -> bool:
        try:
            host = urlparse(url).netloc.lower().split(":")[0]
        except Exception:
            return False
        return bool(_OFFICIAL_DOMAIN.search(host))

    def _needs_facts(self, text: str) -> bool:
        low = text.lower()
        return any(w in low for w in _INSTITUTION_WORDS) or any(
            w in low for w in _FACTUAL_WORDS
        )

    def _institution_query(self, text: str, institution: str, session: EduSession) -> bool:
        """True when the user is asking about a college/university/school."""
        if institution or session.last_institution:
            return True
        if detect_institution(text, session.resolved_entities):
            return True
        return self._needs_facts(text) and any(w in text.lower() for w in _INSTITUTION_WORDS)

    def _is_general_education_query(self, text: str) -> bool:
        low = text.lower()
        return any(re.search(p, low) for p in _GENERAL_QUERY_PATTERNS)

    def _needs_named_institution(
        self,
        text: str,
        analysis: dict[str, Any],
        institution: str,
        session: EduSession,
    ) -> bool:
        """User wants institution-specific facts but did not name which one."""
        # SRKI-only mode: default institution is always SRKI, never ask.
        if settings.edu_focus_srki_only:
            return False
        if institution or session.last_institution:
            return False
        if detect_institution(text, session.resolved_entities):
            return False
        if self._is_general_education_query(text):
            return False

        low = text.lower()
        topic = (analysis.get("topic") or "").lower()
        intents = analysis.get("intents") or []
        intent_blob = " ".join(intents).lower()

        factual = any(w in low for w in _FACTUAL_WORDS) or any(
            k in intent_blob for k in ("admission", "fee", "scholarship", "department", "faculty", "exam", "placement", "contact", "course")
        )
        if not factual:
            return False

        # Named institution from LLM analysis counts as resolved.
        if (analysis.get("institution") or "").strip():
            return False

        # Generic reference: "the university", "my college", "a school" without a proper name.
        if re.search(r"\b(the|my|a|any|some|which)\s+(university|college|school|institute)\b", low):
            return True

        # Factual question with no institution words at all (e.g. "what is the admission process?").
        if not any(w in low for w in _INSTITUTION_WORDS):
            return True

        return False

    def _format_missing_institution_prompt(self, text: str, analysis: dict[str, Any]) -> str:
        topic = (analysis.get("topic") or "").strip() or "your question"
        intents = analysis.get("intents") or []
        intent_hint = ", ".join(intents[:3]).replace("_", " ") if intents else topic

        return (
            "To give you an accurate answer with **official website links**, I need a little more clarity:\n\n"
            "1. **Which university, college, or school** is this about?\n"
            "2. **What exactly** do you want to know? (e.g. admissions, fees, courses, scholarships, "
            "departments, exam dates, contact details)\n\n"
            f"From your message I understood you may be asking about: **{intent_hint}**.\n\n"
            "Please reply with the **institution name** (e.g. VNSGU, Stanford University, Delhi Public School) "
            "and I will fetch **official sources** for that specific institution."
        )

    def _resolve_institution_from_reply(self, text: str, session: EduSession) -> str:
        expanded = expand_institution_aliases(text, session.resolved_entities)
        inst = detect_institution(expanded, session.resolved_entities)
        if inst:
            return inst
        mini = self.llm.analyze(
            f"User is naming a school/college/university for this question: {text}",
            session.history,
        )
        inst = (mini.get("institution") or "").strip()
        if inst:
            return inst
        cleaned = text.strip()
        if cleaned and len(cleaned.split()) <= 8 and not self._is_greeting(cleaned):
            return cleaned
        return ""

    def _merge_institution_query(self, institution: str, saved_query: str, reply: str) -> str:
        blob = " ".join([saved_query, reply, institution]).lower()
        if institution.lower() in blob and institution.lower() in saved_query.lower():
            return saved_query
        if institution.lower() in reply.lower():
            return reply
        return f"{institution} — {saved_query}"

    @staticmethod
    def _link_label(url: str) -> str:
        try:
            host = urlparse(url).netloc.lower().replace("www.", "")
            return host or url
        except Exception:
            return url

    def _boost_analysis_for_institution(
        self, analysis: dict[str, Any], text: str, institution: str
    ) -> None:
        if not institution:
            return
        analysis["needs_web_search"] = True
        topic = (analysis.get("topic") or "").strip()
        extras = [
            f"{institution} official website",
            f"{institution} admissions official site",
        ]
        if topic:
            extras.append(f"{institution} {topic}")
        queries = list(analysis.get("search_queries") or [])
        for q in extras:
            if q not in queries:
                queries.append(q)
        if text not in queries:
            queries.append(text)
        analysis["search_queries"] = queries

    def _build_queries(
        self, text: str, analysis: dict[str, Any], institution: str = ""
    ) -> list[str]:
        queries: list[str] = []
        topic = (analysis.get("topic") or "").strip()
        if institution:
            combined = f"{institution} {topic}".strip() if topic else f"{institution} official website"
            queries.append(combined)
            if not settings.edu_fast_mode:
                queries.append(f"{institution} official website")
                queries.append(f"{institution} admissions")
                low = text.lower()
                if any(w in low for w in ("admission", "fee", "fees", "syllabus", "department", "course")):
                    queries.append(text)
        else:
            queries.append(text)
            if not settings.edu_fast_mode:
                official_probe = f"{text} official website"
                queries.append(official_probe)
        for q in analysis.get("search_queries") or []:
            if q and q not in queries:
                queries.append(q)
        if institution and is_syllabus_query(text):
            queries.insert(0, f"{institution} syllabus pdf official")
            if is_gtu_network(institution):
                queries.insert(0, "site:gtu.ac.in syllabus syllabus.aspx BCA")
            elif is_srki_only(institution):
                queries.insert(0, f"site:srki.ac.in {text} syllabus pdf")
            elif is_su_network(institution):
                domain = get_constituent_primary_domain(institution) or "sarvajanikuniversity.ac.in"
                queries.insert(0, f"site:{domain} {text}")
                if institution == SU:
                    queries.insert(1, f"site:srki.ac.in SU syllabus pdf")
                    queries.insert(2, "site:sarvajanikuniversity.ac.in constituent colleges")
        limit = settings.edu_search_max_queries
        if institution and (is_syllabus_query(text) or is_su_network(institution) or is_srki_only(institution)):
            limit = max(limit, 4)
        return queries[:limit]

    def _ensure_links(
        self,
        reply: str,
        sources: list[str],
        institution: str = "",
        resources: list[dict[str, Any]] | None = None,
    ) -> str:
        """Surface links in reply only when the UI has nothing to show inline."""
        resources = resources or []
        has_rich_media = any(
            r.get("type") in ("pdf", "document", "image") for r in resources
        )
        if has_rich_media or resources:
            return reply
        if not sources and institution:
            return (
                reply
                + f"\n\n**Official sources:** Search \"{institution} official website\" "
                "for the latest verified information."
            )
        if not sources:
            return reply

        lines: list[str] = [""]
        if institution:
            lines.append(f"**Official sources for {institution}:**")
        else:
            lines.append("**Official sources & documents:**")

        official = [u for u in sources if self._is_official(u)]
        ordered = official + [u for u in sources if u not in official]
        for u in ordered[:6]:
            tag = " *(official)*" if self._is_official(u) else ""
            lines.append(f"- [{self._link_label(u)}]({u}){tag}")

        return reply + "\n".join(lines)

    def _ensure_fee_answer(
        self,
        reply: str,
        resources: list[dict[str, Any]] | None,
        institution: str,
        user_query: str,
    ) -> str:
        """Always surface official fees page + embedded fee PDF links."""
        if not is_fee_query(user_query):
            return reply
        fee_pages = get_fee_portal_urls(institution, user_query) or [
            u for u in get_official_urls(institution, user_query) if "fee" in u.lower()
        ]
        fee_pdfs = [
            r
            for r in (resources or [])
            if r.get("type") == "pdf"
            and not is_junk_pdf(r.get("title", ""), r.get("url", ""))
            and any(
                w in f"{r.get('url', '')} {r.get('title', '')}".lower()
                for w in ("fee", "tuition", "payment")
            )
        ]
        if not fee_pdfs:
            fee_pdfs = get_curated_pdf_results(institution, user_query)

        low_reply = (reply or "").lower()
        lines: list[str] = []
        # Prefer a clear official-link block when the model skipped the links.
        needs_page = fee_pages and not any(p.lower() in low_reply for p in fee_pages)
        needs_pdf = fee_pdfs and not any((r.get("url") or "").lower() in low_reply for r in fee_pdfs)
        if not needs_page and not needs_pdf:
            return reply

        lines.append("\n\n**Official SRKI fees sources:**" if institution and "Ramkrishna" in institution else "\n\n**Official fees sources:**")
        for u in fee_pages[:2]:
            if u.lower() not in low_reply:
                lines.append(f"- Fees structure page: [{self._link_label(u)}]({u})")
        for r in fee_pdfs[:2]:
            u = r.get("url") or ""
            if u and u.lower() not in low_reply:
                title = r.get("title") or self._link_label(u)
                lines.append(f"- Official fees PDF: [{title}]({u})")
        if len(lines) <= 1:
            return reply
        return reply + "\n".join(lines)

    def _ensure_syllabus_answer(
        self,
        reply: str,
        resources: list[dict[str, Any]] | None,
        institution: str,
        user_query: str,
    ) -> str:
        if not is_syllabus_query(user_query):
            return reply
        pdfs = [r for r in (resources or []) if r.get("type") == "pdf"]
        pdfs = [r for r in pdfs if not is_junk_pdf(r.get("title", ""), r.get("url", ""))]
        # Strip apologetic "WEB CONTEXT does not contain…" filler when we already have PDFs.
        reply = re.sub(
            r"(?is)\s*(?:unfortunately[, ]+)?(?:the\s+)?(?:provided\s+)?web\s+context\s+does\s+not\s+contain[^.]*\.\s*"
            r"(?:however[^.]*\.\s*)?",
            "\n",
            reply or "",
        )
        reply = re.sub(
            r"(?is)\s*i\s+can\s+guide\s+you\s+on\s+how\s+to\s+find\s+the\s+syllabus[^.]*\.\s*",
            "\n",
            reply,
        )
        low_reply = (reply or "").lower()
        unavailable = any(
            p in low_reply
            for p in (
                "couldn't find",
                "could not find",
                "not available",
                "not found",
                "no syllabus",
                "unable to find",
            )
        )
        # If the model claimed nothing was found but we have matching official PDFs, force the links.
        if pdfs and (unavailable or not any((r.get("url") or "").lower() in low_reply for r in pdfs[:2])):
            if unavailable or not any((r.get("url") or "").lower() in low_reply for r in pdfs[:1]):
                lines = ["\n\n**Official syllabus PDF (from SRKI website):**"]
                for r in pdfs[:2]:
                    u = r.get("url") or ""
                    if not u:
                        continue
                    title = r.get("title") or self._link_label(u)
                    lines.append(f"- [{title}]({u})")
                if len(lines) > 1 and not all((r.get("url") or "").lower() in low_reply for r in pdfs[:1]):
                    reply = reply + "\n".join(lines)
            return reply
        if pdfs:
            return reply
        curated = get_curated_pdf_results(institution, user_query) if institution else []
        if curated:
            lines = ["\n\n**Official syllabus PDF (from SRKI website):**"]
            for r in curated[:2]:
                u = r.get("url") or ""
                title = r.get("title") or self._link_label(u)
                lines.append(f"- [{title}]({u})")
            return reply + "\n".join(lines)
        if institution:
            syllabus_pages = get_syllabus_portal_urls(institution, user_query) or [
                u for u in get_official_urls(institution, user_query) if "syllabus" in u.lower()
            ] or get_official_urls(institution, user_query)[:3]
            lines = [
                "\n\n**📄 Open the official syllabus portal** (select course & semester on the university site):"
            ]
            for u in syllabus_pages[:4]:
                lines.append(f"- [{self._link_label(u)}]({u})")
            return reply + "\n".join(lines)
        return reply

    def _needs_high_accuracy(self, text: str, institution: str) -> bool:
        if is_syllabus_query(text):
            return True
        if not institution:
            return False
        low = text.lower()
        return any(w in low for w in _FACTUAL_WORDS)

    def _resolve_institution_for_query(
        self,
        text: str,
        session: EduSession,
        analysis: dict[str, Any],
        known_institution: str | None,
    ) -> str:
        """Prefer institution named in the CURRENT message over LLM/history."""
        constituent = resolve_constituent(text)
        if constituent:
            return constituent
        llm_inst = (analysis.get("institution") or "").strip()
        if known_institution:
            return known_institution
        if llm_inst:
            return llm_inst
        return (session.last_institution or "").strip()

    def _build_grounding_meta(
        self,
        institution: str,
        sources: list[str],
        resources: list[dict[str, Any]],
        dataset_meta: dict[str, Any] | None,
    ) -> dict[str, Any]:
        pdfs = [r for r in resources if r.get("type") == "pdf"]
        pages = [r for r in resources if r.get("type") == "page"]
        docs = [r for r in resources if r.get("type") == "document"]
        images = [r for r in resources if r.get("type") == "image"]
        parent = get_parent_university(institution) or PARENT_UNIVERSITY.get(institution, "")
        return {
            "institution": institution or None,
            "parent_university": parent or None,
            "pdf_count": len(pdfs),
            "page_count": len(pages),
            "document_count": len(docs),
            "image_count": len(images),
            "link_count": len(sources or []),
            "pdf_read": sum(1 for r in pdfs if r.get("has_content")),
            "dataset_used": bool(dataset_meta),
            "datasets": [dataset_meta["name"]] if dataset_meta else [],
            "sources_summary": " + ".join(
                p
                for p in [
                    f"{len(pdfs)} PDF(s)" if pdfs else "",
                    f"{len(pages)} page(s)" if pages else "",
                    "local dataset" if dataset_meta else "",
                    f"{len(sources or [])} link(s)" if sources else "",
                ]
                if p
            )
            or "web search",
        }

    def _gather_web_context(
        self, queries: list[str], institution: str = "", user_query: str = ""
    ) -> tuple[str, list[str], list[dict[str, Any]]]:
        blocks: list[str] = []
        official: list[str] = []
        others: list[str] = []
        seen: set[str] = set()
        resources: list[dict[str, Any]] = []

        def _add_result(r: dict[str, Any]) -> None:
            url = r.get("url")
            if not url or url in seen:
                return
            if institution and get_institution_domains(institution) and not url_belongs_to_institution(url, institution):
                if not r.get("curated"):
                    return
            seen.add(url)
            tag = "OFFICIAL" if self._is_official(url) or r.get("curated") else "web"
            body = (r.get("extract") or r.get("snippet") or "").strip()
            if body:
                body = body if len(body) <= 700 else body[:700].rsplit(" ", 1)[0] + "…"
                blocks.append(f"[{tag}] {r.get('title') or url}\n{body}\nSource: {url}")
            else:
                blocks.append(f"[{tag}] {r.get('title') or url}\nSource: {url}")
            (official if tag == "OFFICIAL" else others).append(url)

        # Expand course short names (ES→Environmental Science) for matching + LLM grounding.
        nav_query = expand_course_short_names(user_query or "")
        course_note = format_course_resolution_note(user_query or "")
        if course_note:
            blocks.append(f"[OFFICIAL-COURSE-MAP] {course_note}")

        # SRKI Academic → SU Syllabus → UG/PG/PhD official menu flow (deep crawl).
        if institution == SRKI and is_syllabus_query(user_query or ""):
            nav_resources, nav_portals = navigate_srki_syllabus(user_query or "")
            for r in nav_resources:
                url = r.get("url")
                if not url or url in seen:
                    continue
                seen.add(url)
                resources.append(r)
                rtype = r.get("type", "page")
                if rtype == "pdf":
                    blocks.append(
                        f"[OFFICIAL-PDF] {r.get('title') or url}\n"
                        f"Type: PDF | Found via official Academic → SU Syllabus → "
                        f"{'UG' if 'under-graduate' in (r.get('page') or url) else 'PG/PhD'} menu\n"
                        f"Direct link: {url}"
                    )
                    official.append(url)
                else:
                    blocks.append(
                        f"[OFFICIAL-SYLLABUS-PORTAL] {r.get('title') or url}\n"
                        f"Official SRKI syllabus navigation page.\n"
                        f"Direct link: {url}"
                    )
                    official.insert(0, url)
            for u in nav_portals:
                if u not in official:
                    official.insert(0, u)

        # SRKI full site-map topics: scholarship, exam timetable, result, placement, campus, …
        elif institution == SRKI and detect_srki_topics(user_query or ""):
            for r in navigate_srki_topic(user_query or ""):
                url = r.get("url")
                if not url or url in seen:
                    continue
                seen.add(url)
                resources.append(r)
                rtype = r.get("type", "page")
                if rtype == "pdf":
                    blocks.append(
                        f"[OFFICIAL-PDF] {r.get('title') or url}\n"
                        f"Type: PDF | From official SRKI menu page\n"
                        f"Direct link: {url}"
                    )
                    official.append(url)
                else:
                    blocks.append(
                        f"[OFFICIAL-PAGE] {r.get('title') or url}\n"
                        f"Official SRKI website menu page.\n"
                        f"Direct link: {url}"
                    )
                    official.insert(0, url)

        # Curated official links first (works even when DuckDuckGo is blocked on cloud hosts).
        if institution:
            for r in get_portal_page_resources(institution, nav_query or user_query or ""):
                url = r.get("url")
                if not url or url in seen:
                    continue
                seen.add(url)
                resources.insert(0, r)
                blocks.insert(
                    0,
                    f"[OFFICIAL-SYLLABUS-PORTAL] {r.get('title') or url}\n"
                    f"Official syllabus selection page on the institution website. "
                    f"Open this link to select course, branch, and semester (same as Google search result).\n"
                    f"Direct link: {url}",
                )
                official.insert(0, url)
            for r in get_official_search_results(institution, user_query or institution):
                _add_result(r)
            # Prefer PDFs found via Academic → SU Syllabus menu; only add curated if none yet.
            has_nav_pdfs = any(r.get("source") == "srki_syllabus_nav" and r.get("type") == "pdf" for r in resources)
            if not has_nav_pdfs:
                for r in get_curated_pdf_results(institution, user_query or ""):
                    if r.get("url") and r["url"] not in seen and not is_junk_pdf(r.get("title", ""), r["url"]):
                        resources.append(r)
                        blocks.append(
                            f"[OFFICIAL-PDF] {r.get('title') or r['url']}\n"
                            f"Type: PDF | Curated official syllabus document\n"
                            f"Direct link: {r['url']}"
                        )
                        official.append(r["url"])
                        seen.add(r["url"])

        # Parallel web search (2 queries max in fast mode).
        for r in search_many_parallel(queries):
            _add_result(r)

        # Only discover extra URLs if we still have nothing official.
        if institution and len(official) < 2:
            for u in find_official_urls_for_institution(institution, user_query):
                _add_result(
                    {
                        "url": u,
                        "title": f"{institution} — official site",
                        "snippet": f"Official website for {institution}.",
                        "curated": True,
                    }
                )

        # Quick PDF/page scan on official pages.
        seed_pages = [u for u in official[:2]] or [u for u in others[:1]]
        if institution and not seed_pages:
            seed_pages = find_official_urls_for_institution(institution, user_query)[:1]
        contact_q = is_contact_query(user_query or "")
        fee_q = is_fee_query(user_query or "")
        admission_q = is_admission_query(user_query or "")
        # "Fee only" strictness must not apply to multi-intent questions
        # like "admission process and fees structure".
        fee_only_q = fee_q and not admission_q
        wants_media = query_wants_document_media(user_query or "")
        if institution and (is_srki_only(institution) or is_su_network(institution)):
            if contact_q and not wants_media:
                # Address/contact: only official contact (and default) pages — not syllabus hubs.
                seed_pages = list(
                    dict.fromkeys(get_official_urls(institution, user_query) + official)
                )[:3]
            elif fee_q:
                # Fees: prioritize fees-structure / payment pages so iframe PDF is discovered.
                seeds = get_official_urls(institution, user_query) + official
                if admission_q:
                    # Multi-intent: fee page first, then admission pages — keep both topics.
                    seeds = get_fee_portal_urls(institution, user_query) + seeds
                    seed_pages = list(dict.fromkeys(seeds))[:6]
                else:
                    seed_pages = list(dict.fromkeys(seeds))[:4]
            elif is_syllabus_query(user_query or "") and institution == SRKI:
                # Follow Academic → SU Syllabus → UG/PG pages, then department pages.
                from backend.app.pipeline.srki_syllabus_nav import (
                    _UG,
                    _PG,
                    _PHD,
                    _SU_SYLLABUS,
                    detect_level_from_query,
                )

                level = detect_level_from_query(user_query or "")
                level_url = {"ug": _UG, "pg": _PG, "phd": _PHD}.get(level, _UG)
                dept = get_srki_department_urls_for_query(nav_query or user_query or "")
                seeds = (
                    [_SU_SYLLABUS, level_url]
                    + dept
                    + get_syllabus_portal_urls(institution, user_query)
                    + get_official_urls(institution, user_query)
                    + official
                    + get_crawl_seed_urls(institution, [], nav_query or user_query)
                )
                seed_pages = list(dict.fromkeys(seeds))[:8]
            else:
                seed_pages = list(
                    dict.fromkeys(
                        get_official_urls(institution, user_query)
                        + official
                        + get_crawl_seed_urls(institution, [], user_query)
                    )
                )[: get_asset_harvest_pages(institution)]
        if seed_pages and settings.external_search_enabled:
            max_pg = 2 if (contact_q and not wants_media) else max(
                settings.edu_asset_harvest_pages, get_asset_harvest_pages(institution)
            )
            if fee_q:
                max_pg = max(max_pg, 5 if admission_q else 3)
            if is_syllabus_query(user_query or "") and institution == SRKI:
                max_pg = max(max_pg, 5)
            harvested = harvest_official_assets(
                seed_pages[:max_pg],
                user_query or institution or (queries[0] if queries else ""),
                max_pages=max_pg,
            )
            if contact_q and not wants_media:
                harvested = [
                    h
                    for h in harvested
                    if h.get("type") == "page"
                    or any(
                        w in f"{h.get('url', '')} {h.get('title', '')}".lower()
                        for w in ("contact", "address", "map", "location")
                    )
                ]
            elif fee_only_q:
                harvested = [
                    h
                    for h in harvested
                    if h.get("type") in ("pdf", "document")
                    or any(
                        w in f"{h.get('url', '')} {h.get('title', '')}".lower()
                        for w in ("fee", "fees", "tuition", "payment")
                    )
                ]
            resources.extend(harvested)
            tag_map = {"pdf": "OFFICIAL-PDF", "document": "OFFICIAL-DOC", "page": "OFFICIAL-PAGE", "image": "OFFICIAL-IMAGE"}
            for r in resources:
                url = r.get("url")
                if not url or url in seen:
                    continue
                seen.add(url)
                rtype = r.get("type", "page")
                tag = tag_map.get(rtype, "OFFICIAL")
                blocks.append(
                    f"[{tag}] {r.get('title') or url}\n"
                    f"Type: {rtype.upper()} | From page: {r.get('page_title') or r.get('page')}\n"
                    f"Direct link: {url}"
                )
                if tag.startswith("OFFICIAL"):
                    official.append(url)
                else:
                    others.append(url)

            # Crawl official menus/sub-menus for PDFs, pages, and informative images.
            # Skip deep media crawl for contact/address-only questions.
            if institution and not (contact_q and not wants_media) and not fee_only_q:
                nav_seeds = get_crawl_seed_urls(
                    institution,
                    list(dict.fromkeys(get_official_urls(institution, user_query) + seed_pages + official[:6])),
                    user_query,
                )
                crawl = crawl_official_site(nav_seeds, user_query or institution, institution)
                existing = {r.get("url") for r in resources}
                for r in crawl.get("pdfs", []) + crawl.get("pages", []) + crawl.get("images", []):
                    url = r.get("url")
                    if not url or url in seen or url in existing:
                        continue
                    if not wants_media and r.get("type") in ("pdf", "document", "image"):
                        continue
                    seen.add(url)
                    existing.add(url)
                    resources.append(r)
                    rtype = r.get("type", "page")
                    if rtype == "pdf":
                        blocks.append(
                            f"[OFFICIAL-PDF] {r.get('title') or url}\n"
                            f"Type: PDF | Found via official site menu navigation\n"
                            f"Direct link: {url}"
                        )
                        official.append(url)
                    elif rtype == "image":
                        blocks.append(
                            f"[OFFICIAL-IMAGE] {r.get('title') or url}\n"
                            f"Informative image from official website navigation\n"
                            f"Direct link: {url}"
                        )
                        official.append(url)
                    else:
                        blocks.append(
                            f"[OFFICIAL-PAGE] {r.get('title') or url}\n"
                            f"Relevant official sub-page from site navigation\n"
                            f"Direct link: {url}"
                        )
                        official.append(url)

                # Fetch readable text from top official pages for accurate answers.
                extract_urls: list[str] = []
                for u in official[:3]:
                    if u not in extract_urls and _asset_type(u) != "pdf":
                        extract_urls.append(u)
                for p in crawl.get("pages", [])[: settings.edu_official_page_extracts]:
                    u = p.get("url", "")
                    if u and u not in extract_urls:
                        extract_urls.append(u)
                for page_url in extract_urls[: settings.edu_official_page_extracts + 1]:
                    extract = fetch_page_extract(page_url, user_query or institution, max_len=1400)
                    if extract:
                        blocks.append(
                            f"[OFFICIAL-PAGE-CONTENT] {page_url}\n"
                            f"Extracted from official website page (use for verified facts):\n"
                            f"{extract}\n"
                            f"Source: {page_url}"
                        )
            elif institution and (contact_q or fee_q or admission_q):
                # Contact/fee/admission: extract text from the topic pages for accurate answers.
                extract_urls = []
                for u in seed_pages + official:
                    if u and u not in extract_urls and _asset_type(u) != "pdf":
                        extract_urls.append(u)
                for page_url in extract_urls[: 4 if (fee_q and admission_q) else 3]:
                    extract = fetch_page_extract(page_url, user_query or institution, max_len=1400)
                    if extract:
                        blocks.append(
                            f"[OFFICIAL-PAGE-CONTENT] {page_url}\n"
                            f"Extracted from official website page (use for verified facts):\n"
                            f"{extract}\n"
                            f"Source: {page_url}"
                        )

        # Read PDF text so answers can be grounded in official documents.
        if resources and wants_media:
            query_for_pdf = user_query or institution or (queries[0] if queries else "")
            max_pdfs = 1 if is_syllabus_query(user_query or "") else settings.edu_pdf_max_read
            if fee_q:
                max_pdfs = max(max_pdfs, 1)
            if is_syllabus_query(user_query or "") and (
                is_su_network(institution) or is_vnsgu_network(institution) or is_gtu_network(institution)
            ):
                max_pdfs = max(max_pdfs, 2)
            resources = enrich_pdf_resources(
                resources, query_for_pdf, max_pdfs=max_pdfs, institution=institution
            )
            for pdf_block in format_pdf_context_blocks(resources):
                blocks.append(pdf_block)

        if institution:
            resources = filter_resources_for_institution(resources, institution)
            official = filter_urls_for_institution(official, institution)
            others = [u for u in others if url_belongs_to_institution(u, institution) or self._is_official(u)]

        resources = filter_resources_for_query(resources, user_query or "")
        # Prefer official contact / fee URLs first for those queries.
        if contact_q:
            contact_urls = [u for u in official if "contact" in u.lower()]
            other_off = [u for u in official if u not in contact_urls]
            official = contact_urls + other_off
        if fee_q:
            fee_urls = [u for u in official if "fee" in u.lower()]
            other_off = [u for u in official if u not in fee_urls]
            official = fee_urls + other_off

        sources = list(dict.fromkeys(official + others))
        sources = filter_sources_for_query(sources, user_query or "", resources)
        return "\n\n---\n\n".join(blocks), sources, resources

    def chat(self, session_id: str, message: str) -> dict[str, Any]:
        if not self.ready:
            return {"reply": NOT_CONFIGURED_REPLY, "intent": None, "source": "unconfigured"}

        session = self.get_session(session_id)
        text = preprocess(message)

        if self._is_greeting(text):
            greeting = GREETING_REPLY if settings.edu_focus_srki_only else GREETING_REPLY_GENERAL
            session.history.append({"role": "user", "content": text})
            session.history.append({"role": "assistant", "content": greeting})
            return {
                "reply": greeting,
                "intent": "general_greeting",
                "intents": ["general_greeting"],
                "is_multi_intent": False,
                "role": "student",
                "context": {"Topic": ["greeting"]},
                "source": "greeting",
            }

        reconcile_resolutions(text, session.resolved_entities)

        # --- User was asked which university/college/school ---
        if session.pending_institution_name:
            saved_query = session.pending_institution_query or ""
            institution = self._resolve_institution_from_reply(text, session)
            if institution:
                session.pending_institution_name = False
                session.pending_institution_query = None
                session.last_institution = institution
                merged = self._merge_institution_query(institution, saved_query, text)
                merged = expand_institution_aliases(merged, session.resolved_entities)
                return self._answer_resolved(session, merged)
            prompt = (
                "I still need the **name of the university, college, or school** to provide "
                "official links.\n\nPlease reply with the institution name "
                "(e.g. **VNSGU**, **Harvard University**, **Delhi Public School**)."
            )
            session.history.append({"role": "user", "content": text})
            session.history.append({"role": "assistant", "content": prompt})
            return {
                "reply": prompt,
                "intent": "clarification",
                "intents": ["missing_institution"],
                "needs_clarification": True,
                "context": {"Topic": ["institution_clarification"]},
                "source": "clarification",
            }

        # --- Web-resolved institution follow-up (unknown short name from search) ---
        if session.pending_web_institution:
            token = session.pending_web_institution.get("token", "")
            options = session.pending_web_institution.get("options") or []
            needed = {token: options} if token and options else {}
            resolved = resolve_institution_from_reply(text, needed)
            if not resolved:
                reply = format_web_institution_clarification(token, options)
                return {
                    "reply": reply,
                    "intent": "clarification",
                    "intents": ["institution_web_clarification"],
                    "needs_clarification": True,
                    "clarification_options": build_clarification_options(
                        web_token=token, web_options=options
                    ),
                    "context": {"Topic": ["web_institution_clarification"]},
                    "source": "clarification",
                }
            session.resolved_entities.update(resolved)
            session.last_institution = next(iter(resolved.values()))
            session.pending_web_institution = {}
            text = session.pending_query or text
            session.pending_query = None
            text = expand_institution_aliases(
                apply_resolutions(text, session.resolved_entities),
                session.resolved_entities,
            )
            return self._answer_resolved(session, text)

        # --- Disambiguation follow-up (user picked an option) ---
        if session.pending_institution or session.pending_course:
            saved_inst = dict(session.pending_institution)
            saved_course = dict(session.pending_course)
            saved_query = session.pending_query
            inst_resolved = resolve_institution_from_reply(text, saved_inst)
            course_resolved = resolve_from_reply(text, saved_course)
            if not inst_resolved and not course_resolved:
                reply = format_institution_clarification(saved_inst) or format_clarification(saved_course)
                return {
                    "reply": reply or "Please pick one of the numbered options so I can continue.",
                    "intent": "clarification",
                    "needs_clarification": True,
                    "clarification_options": build_clarification_options(
                        institution_needed=saved_inst or None,
                        course_needed=saved_course or None,
                    ),
                    "source": "clarification",
                }
            session.resolved_entities.update(inst_resolved)
            session.resolved_entities.update(course_resolved)
            session.pending_institution = {}
            session.pending_course = {}
            if inst_resolved:
                session.last_institution = next(iter(inst_resolved.values()))
            text = saved_query or text
            session.pending_query = None
            text = expand_institution_aliases(
                apply_resolutions(text, session.resolved_entities),
                session.resolved_entities,
            )
            return self._answer_resolved(session, text)

        # Expand unambiguous short names early (VNSGU, SRKI, IIT Bombay, …).
        text = expand_institution_aliases(
            apply_resolutions(text, session.resolved_entities),
            session.resolved_entities,
        )

        # Auto-resolve bare SU → Sarvajanik University in Gujarat/Surat context.
        bare_su = resolve_bare_su(text)
        if bare_su:
            session.resolved_entities["su"] = bare_su
            if not session.last_institution:
                session.last_institution = bare_su
            text = expand_institution_aliases(text, session.resolved_entities)

        # --- Unknown short name: search the web to identify the institution ---
        if not settings.edu_focus_srki_only and not detect_institution(text, session.resolved_entities):
            unknown_tokens = find_unknown_institution_tokens(text, session.resolved_entities)
            if unknown_tokens:
                token = unknown_tokens[0]
                candidates = search_institution_by_short_name(token, text)
                if len(candidates) == 1:
                    session.resolved_entities[token] = candidates[0]["resolution"]
                    session.last_institution = candidates[0]["resolution"]
                    text = expand_institution_aliases(text, session.resolved_entities)
                elif len(candidates) > 1:
                    session.pending_web_institution = {"token": token, "options": candidates}
                    session.pending_query = text
                    reply = format_web_institution_clarification(token, candidates)
                    session.history.append({"role": "user", "content": text})
                    session.history.append({"role": "assistant", "content": reply})
                    return {
                        "reply": reply,
                        "intent": "clarification",
                        "intents": ["institution_web_clarification"],
                        "needs_clarification": True,
                        "clarification_options": build_clarification_options(
                            web_token=token, web_options=candidates
                        ),
                        "context": {"Topic": ["web_institution_clarification"]},
                        "source": "web_institution_lookup",
                    }

        # --- Detect ambiguous abbreviations (homographs) ---
        inst_ambiguous = {} if settings.edu_focus_srki_only else find_ambiguous_institutions(
            text, session.resolved_entities
        )
        for term in list(inst_ambiguous.keys()):
            from_hist = resolve_from_history(
                term, session.history, session.resolved_entities, session.last_institution
            )
            if from_hist:
                session.resolved_entities[term] = from_hist
                session.last_institution = from_hist
                del inst_ambiguous[term]

        course_ambiguous = find_ambiguous_terms(text, session.resolved_entities)

        if inst_ambiguous or course_ambiguous:
            session.pending_institution = inst_ambiguous
            session.pending_course = course_ambiguous
            session.pending_query = text
            parts = []
            if inst_ambiguous:
                parts.append(format_institution_clarification(inst_ambiguous))
            if course_ambiguous:
                parts.append(format_clarification(course_ambiguous))
            return {
                "reply": "\n\n".join(parts),
                "intent": "clarification",
                "intents": ["clarification"],
                "needs_clarification": True,
                "clarification_options": build_clarification_options(
                    institution_needed=inst_ambiguous or None,
                    course_needed=course_ambiguous or None,
                ),
                "context": {
                    "PendingDisambiguation": list(inst_ambiguous.keys()) + list(course_ambiguous.keys())
                },
                "source": "disambiguation",
            }

        return self._answer_resolved(session, text)

    def _answer_resolved(self, session: EduSession, text: str) -> dict[str, Any]:
        known_institution = detect_institution(text, session.resolved_entities)
        analysis = self.llm.analyze(text, session.history)

        if not analysis.get("is_education", True):
            return {
                "reply": OFF_TOPIC_REPLY,
                "intent": "off_topic",
                "intents": ["off_topic"],
                "is_multi_intent": False,
                "role": analysis.get("user_role"),
                "context": {"Topic": ["out_of_domain"]},
                "source": "domain_guard",
            }

        clarification = analysis.get("clarification")
        institution = self._resolve_institution_for_query(
            text, session, analysis, known_institution
        )

        # SRKI-only mode: answer SRKI queries; politely scope-limit other institutions.
        if settings.edu_focus_srki_only:
            low = text.lower()
            mentions_srki = bool(re.search(r"\bsrki\b|\bramkrishna\b", low))
            if mentions_srki or not institution:
                institution = SRKI
                clarification = None
            elif institution != SRKI:
                session.last_institution = SRKI
                session.history.append({"role": "user", "content": text})
                session.history.append({"role": "assistant", "content": SRKI_SCOPE_REPLY})
                return {
                    "reply": SRKI_SCOPE_REPLY,
                    "intent": "out_of_scope_institution",
                    "intents": ["out_of_scope_institution"],
                    "is_multi_intent": False,
                    "role": analysis.get("user_role"),
                    "context": {"Topic": ["srki_scope_limit"], "RequestedInstitution": [institution]},
                    "source": "scope_guard",
                }

        if self._needs_named_institution(text, analysis, institution, session):
            reply = self._format_missing_institution_prompt(text, analysis)
            session.pending_institution_name = True
            session.pending_institution_query = text
            session.history.append({"role": "user", "content": text})
            session.history.append({"role": "assistant", "content": reply})
            intents = analysis.get("intents") or ["clarification"]
            return {
                "reply": reply,
                "intent": "clarification",
                "intents": intents,
                "role": analysis.get("user_role"),
                "context": self._pragmatic_context(analysis, intents, ""),
                "needs_clarification": True,
                "source": "institution_clarification",
            }

        if clarification and not institution:
            session.pending_institution_name = True
            session.pending_institution_query = text
            session.history.append({"role": "user", "content": text})
            session.history.append({"role": "assistant", "content": clarification})
            return {
                "reply": clarification,
                "intent": "clarification",
                "intents": analysis.get("intents"),
                "role": analysis.get("user_role"),
                "context": self._pragmatic_context(analysis, analysis.get("intents") or [], ""),
                "needs_clarification": True,
                "source": "clarification",
            }

        if clarification:
            return {
                "reply": clarification,
                "intent": "clarification",
                "intents": analysis.get("intents"),
                "role": analysis.get("user_role"),
                "context": self._pragmatic_context(analysis, analysis.get("intents") or [], ""),
                "needs_clarification": True,
                "source": "clarification",
            }

        if institution:
            session.last_institution = institution
            analysis["institution"] = institution
            self._boost_analysis_for_institution(analysis, text, institution)

        # Curated accurate answer for SRKI courses-offered list queries
        # (from the official courses page — avoids partial lists from stray PDFs).
        if is_courses_offered_query(text) and institution == SRKI:
            reply, resources, sources = format_srki_courses_answer()
            session.last_institution = SRKI
            session.history.append({"role": "user", "content": text})
            session.history.append({"role": "assistant", "content": reply})
            intents = analysis.get("intents") or ["courses_offered"]
            grounding = self._build_grounding_meta(SRKI, sources, resources, None)
            return {
                "reply": reply,
                "intent": "courses_offered",
                "intents": intents,
                "is_multi_intent": bool(analysis.get("is_multi_intent")),
                "role": analysis.get("user_role"),
                "institution": SRKI,
                "context": self._pragmatic_context(analysis, intents, SRKI),
                "confidence": 1.0,
                "sources": sources,
                "resources": resources,
                "grounding": grounding,
                "source": "curated_catalog",
            }

        # Curated accurate answer for SU constituent-college list queries.
        if is_constituent_list_query(text) and (
            institution == SU or is_su_network(institution) or resolve_bare_su(text) == SU
        ):
            reply, resources, sources = format_su_constituent_colleges_answer()
            session.last_institution = SU
            session.history.append({"role": "user", "content": text})
            session.history.append({"role": "assistant", "content": reply})
            intents = analysis.get("intents") or ["constituent_colleges"]
            grounding = self._build_grounding_meta(SU, sources, resources, None)
            return {
                "reply": reply,
                "intent": "constituent_colleges",
                "intents": intents,
                "is_multi_intent": False,
                "role": analysis.get("user_role"),
                "institution": SU,
                "context": self._pragmatic_context(analysis, intents, SU),
                "confidence": 1.0,
                "sources": sources,
                "resources": resources,
                "grounding": grounding,
                "source": "curated_su_constituents",
            }

        is_institution_q = self._institution_query(text, institution, session)
        force_web = is_institution_q or self._needs_facts(text) or bool(institution)
        web_context, sources = "", []
        resources: list[dict[str, Any]] = []
        dataset_meta: dict[str, Any] | None = None
        local_block, dataset_meta = try_local_curriculum_block(
            text, institution, session.resolved_entities
        )
        if force_web or analysis.get("needs_web_search"):
            queries = self._build_queries(text, analysis, institution)
            web_context, sources, resources = self._gather_web_context(queries, institution, text)
        if local_block:
            web_context = (local_block + "\n\n---\n\n" + web_context).strip() if web_context else local_block

        reply = self.llm.generate(
            text,
            analysis,
            web_context,
            session.history,
            high_accuracy=self._needs_high_accuracy(text, institution),
            institution=institution,
        )
        # Remove internal grounding tags if the model echoes them.
        reply = re.sub(r"\[OFFICIAL-[A-Z0-9_-]+\]", "", reply or "")
        reply = re.sub(r"\n{3,}", "\n\n", reply).strip()
        reply = self._ensure_links(reply, sources, institution, resources)
        reply = self._ensure_fee_answer(reply, resources, institution, text)
        reply = self._ensure_syllabus_answer(reply, resources, institution, text)
        sources = filter_sources_for_query(sources or [], text, resources or [])
        resources = filter_resources_for_query(resources or [], text)

        session.history.append({"role": "user", "content": text})
        session.history.append({"role": "assistant", "content": reply})
        max_msgs = settings.edu_history_turns * 2
        if len(session.history) > max_msgs:
            session.history = session.history[-max_msgs:]

        intents = analysis.get("intents") or []
        context = self._pragmatic_context(analysis, intents, institution)
        if session.resolved_entities:
            context["ResolvedTerms"] = dict(session.resolved_entities)
        grounding = self._build_grounding_meta(institution, sources or [], resources or [], dataset_meta)
        return {
            "reply": reply,
            "intent": intents[0] if intents else "general_query",
            "intents": intents,
            "is_multi_intent": analysis.get("is_multi_intent", len(intents) > 1),
            "role": analysis.get("user_role"),
            "institution": institution or None,
            "context": context,
            "confidence": 1.0,
            "sources": sources or None,
            "resources": resources or None,
            "grounding": grounding,
            "source": "llm+web" if sources else "llm",
        }

    def _pragmatic_context(
        self, analysis: dict[str, Any], intents: list[str], institution: str
    ) -> dict[str, Any]:
        """Entity/context JSON saved to the database (like Course / Institution in research UI)."""
        ctx: dict[str, Any] = {}
        if institution:
            ctx["Institution"] = [institution]
        topic = (analysis.get("topic") or "").strip()
        if topic:
            ctx["Topic"] = [topic]
        role = analysis.get("user_role")
        if role and role != "other":
            ctx["Role"] = [role.title()]
        if intents:
            ctx["IntentLabels"] = intents
        return ctx
