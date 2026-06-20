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
from backend.app.pipeline.preprocessing import preprocess
from backend.app.pipeline.web_search import search_with_grounding

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

# Official / authoritative domains to surface first.
_OFFICIAL_DOMAIN = re.compile(
    r"(\.edu|\.gov|\.ac\.[a-z]{2,3}|\.edu\.[a-z]{2,3}|\.gov\.[a-z]{2,3})$"
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

    def _build_queries(
        self, text: str, analysis: dict[str, Any], institution: str = ""
    ) -> list[str]:
        queries: list[str] = []
        # When a specific institution is named, probe its official website first.
        if institution:
            queries.append(f"{institution} official website")
            topic = (analysis.get("topic") or "").strip()
            queries.append(f"{institution} {topic}".strip() if topic else institution)
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
        return queries[: settings.edu_search_max_queries + 1]

    def _ensure_links(self, reply: str, sources: list[str]) -> str:
        """Guarantee the answer carries at least one valid link when we have sources."""
        if not sources:
            return reply
        if re.search(r"https?://", reply):
            return reply  # model already cited links
        official = [u for u in sources if self._is_official(u)]
        lines = ["", "**Sources / official links:**"]
        ordered = (official or []) + [u for u in sources if u not in official]
        for u in ordered[:5]:
            tag = " (official)" if self._is_official(u) else ""
            lines.append(f"- {u}{tag}")
        return reply + "\n" + "\n".join(lines)

    def _gather_web_context(self, queries: list[str]) -> tuple[str, list[str]]:
        blocks: list[str] = []
        official: list[str] = []
        others: list[str] = []
        seen: set[str] = set()
        for q in queries:
            payload = search_with_grounding(q)
            for r in (payload.get("results") or [])[:4]:
                url = r.get("url")
                body = (r.get("extract") or r.get("snippet") or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                tag = "OFFICIAL" if self._is_official(url) else "web"
                if body:
                    snippet = body if len(body) <= 700 else body[:700].rsplit(" ", 1)[0] + "…"
                    blocks.append(f"[{tag}] {r.get('title') or url}\n{snippet}\nSource: {url}")
                (official if tag == "OFFICIAL" else others).append(url)
        # Official links first so the model and the UI surface them prominently.
        sources = official + others
        return "\n\n---\n\n".join(blocks), sources

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

        institution = (analysis.get("institution") or known_institution or "").strip()
        if institution:
            session.last_institution = institution
        force_web = self._needs_facts(text) or bool(institution)
        web_context, sources = "", []
        if force_web or analysis.get("needs_web_search"):
            queries = self._build_queries(text, analysis, institution)
            web_context, sources = self._gather_web_context(queries)

        reply = self.llm.generate(text, analysis, web_context, session.history)
        reply = self._ensure_links(reply, sources)

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
