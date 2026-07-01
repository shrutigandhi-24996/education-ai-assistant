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
from backend.app.pipeline.institution_disambiguation import (
    detect_institution,
    expand_institution_aliases,
    find_ambiguous_institutions,
    format_institution_clarification,
    resolve_from_history,
    resolve_institution_from_reply,
)
from backend.app.pipeline.llm_client import LLMClient
from backend.app.pipeline.official_links import get_official_search_results
from backend.app.pipeline.page_assets import harvest_official_assets
from backend.app.pipeline.preprocessing import preprocess
from backend.app.pipeline.web_search import find_official_urls_for_institution, search_with_grounding

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
    "I'm the **Innovative Educational Chatbot** — I focus on education topics: admissions, "
    "colleges & universities, schools, courses, scholarships, exams, departments, faculty, "
    "fees, results, and career guidance.\n\n"
    "Your question seems outside this domain. Please ask me something related to education "
    "and I'll search official sources to help you."
)

GREETING_REPLY = """Hello! Welcome to the **Innovative Educational Chatbot**.

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
        # When a specific institution is named, probe its official website first.
        if institution:
            queries.append(f"{institution} official website")
            queries.append(f"{institution} admissions")
            topic = (analysis.get("topic") or "").strip()
            queries.append(f"{institution} {topic}".strip() if topic else institution)
            low = text.lower()
            if any(w in low for w in ("admission", "apply", "brochure", "prospectus")):
                queries.append(f"{institution} admission brochure pdf")
            if any(w in low for w in ("fee", "fees", "tuition")):
                queries.append(f"{institution} fee structure pdf")
            if "syllabus" in low or "curriculum" in low:
                queries.append(f"{institution} syllabus pdf")
            if "department" in low or "course" in low:
                queries.append(f"{institution} department course details pdf")
        # The LLM's own suggestions next (often well-scoped).
        for q in analysis.get("search_queries") or []:
            if q and q not in queries:
                queries.append(q)
        # Always include the raw question and a generic official-website probe.
        if text not in queries:
            queries.append(text)
        official_probe = f"{text} official website"
        if not institution and official_probe not in queries:
            queries.append(official_probe)
        return queries[: max(settings.edu_search_max_queries + 2, 5)]

    def _ensure_links(
        self,
        reply: str,
        sources: list[str],
        institution: str = "",
        resources: list[dict[str, Any]] | None = None,
    ) -> str:
        """Always surface clickable official links, PDFs, and page assets."""
        resources = resources or []
        if not sources and not resources and institution:
            return (
                reply
                + f"\n\n**Official sources:** Search \"{institution} official website\" "
                "for the latest verified information."
            )
        if not sources and not resources:
            return reply

        lines: list[str] = [""]
        if institution:
            lines.append(f"**Official sources for {institution}:**")
        else:
            lines.append("**Official sources & documents:**")

        pdfs = [r for r in resources if r.get("type") == "pdf"]
        docs = [r for r in resources if r.get("type") == "document"]
        pages = [r for r in resources if r.get("type") == "page"]
        images = [r for r in resources if r.get("type") == "image"]

        if pdfs:
            lines.append("\n**📄 Official PDFs (open directly):**")
            for r in pdfs[:6]:
                lines.append(f"- [{r.get('title', 'PDF')}]({r['url']})")
        if docs:
            lines.append("\n**📁 Official documents:**")
            for r in docs[:4]:
                lines.append(f"- [{r.get('title', 'Document')}]({r['url']})")
        if pages:
            lines.append("\n**🌐 Official web pages:**")
            for r in pages[:5]:
                lines.append(f"- [{r.get('title', self._link_label(r['url']))}]({r['url']})")
        if images:
            lines.append("\n**🖼️ Informative images:**")
            for r in images[:3]:
                lines.append(f"- [{r.get('title', 'Image')}]({r['url']})")

        official = [u for u in sources if self._is_official(u)]
        ordered = official + [u for u in sources if u not in official]
        extra = [u for u in ordered if u not in {r["url"] for r in resources}][:6]
        if extra:
            lines.append("\n**🔗 Additional official links:**")
            for u in extra:
                tag = " *(official)*" if self._is_official(u) else ""
                lines.append(f"- [{self._link_label(u)}]({u}){tag}")

        return reply + "\n".join(lines)

    def _gather_web_context(
        self, queries: list[str], institution: str = "", user_query: str = ""
    ) -> tuple[str, list[str], list[dict[str, Any]]]:
        blocks: list[str] = []
        official: list[str] = []
        others: list[str] = []
        seen: set[str] = set()

        def _add_result(r: dict[str, Any]) -> None:
            url = r.get("url")
            if not url or url in seen:
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

        # Curated official links first (works even when DuckDuckGo is blocked on cloud hosts).
        if institution:
            for r in get_official_search_results(institution, user_query or institution):
                _add_result(r)

        for q in queries:
            payload = search_with_grounding(q)
            for r in (payload.get("results") or [])[:4]:
                _add_result(r)

        if institution and not official and not others:
            payload = search_with_grounding(f"{institution} official website")
            for r in (payload.get("results") or [])[:3]:
                _add_result(r)

        # Discover official domains for ANY institution (works when HTML search fails on cloud).
        if institution:
            for u in find_official_urls_for_institution(institution, user_query):
                _add_result(
                    {
                        "url": u,
                        "title": f"{institution} — official site",
                        "snippet": f"Official website for {institution}.",
                        "curated": True,
                    }
                )

        # Harvest PDFs, documents, images, and relevant sub-pages from official sites.
        resources: list[dict[str, Any]] = []
        seed_pages = [u for u in official[:3]] or [u for u in others[:2]]
        if institution and not seed_pages:
            seed_pages = find_official_urls_for_institution(institution, user_query)[:2]
        if seed_pages:
            resources = harvest_official_assets(
                seed_pages[:2], user_query or institution or queries[0], max_pages=2
            )
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

        sources = list(dict.fromkeys(official + others))
        return "\n\n---\n\n".join(blocks), sources, resources

    def chat(self, session_id: str, message: str) -> dict[str, Any]:
        if not self.ready:
            return {"reply": NOT_CONFIGURED_REPLY, "intent": None, "source": "unconfigured"}

        session = self.get_session(session_id)
        text = preprocess(message)

        if self._is_greeting(text):
            session.history.append({"role": "user", "content": text})
            session.history.append({"role": "assistant", "content": GREETING_REPLY})
            return {
                "reply": GREETING_REPLY,
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

        # Expand unambiguous short names early (VNSGU, IIT Bombay, …).
        text = expand_institution_aliases(
            apply_resolutions(text, session.resolved_entities),
            session.resolved_entities,
        )

        # --- Detect ambiguous abbreviations (homographs) ---
        inst_ambiguous = find_ambiguous_institutions(text, session.resolved_entities)
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
                "needs_clarification": True,
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
        institution = (
            (analysis.get("institution") or known_institution or session.last_institution or "")
            .strip()
        )

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
            self._boost_analysis_for_institution(analysis, text, institution)

        is_institution_q = self._institution_query(text, institution, session)
        force_web = is_institution_q or self._needs_facts(text) or bool(institution)
        web_context, sources = "", []
        resources: list[dict[str, Any]] = []
        if force_web or analysis.get("needs_web_search"):
            queries = self._build_queries(text, analysis, institution)
            web_context, sources, resources = self._gather_web_context(queries, institution, text)

        reply = self.llm.generate(text, analysis, web_context, session.history)
        reply = self._ensure_links(reply, sources, institution, resources)

        session.history.append({"role": "user", "content": text})
        session.history.append({"role": "assistant", "content": reply})
        max_msgs = settings.edu_history_turns * 2
        if len(session.history) > max_msgs:
            session.history = session.history[-max_msgs:]

        intents = analysis.get("intents") or []
        context = self._pragmatic_context(analysis, intents, institution)
        if session.resolved_entities:
            context["ResolvedTerms"] = dict(session.resolved_entities)
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
