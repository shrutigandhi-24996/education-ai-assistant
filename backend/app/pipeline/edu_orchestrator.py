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
    "I'm an **Education assistant** — I help with admissions, colleges & universities, "
    "courses, scholarships, exams, departments, faculty, fees, results, and career "
    "guidance. Ask me anything in that space and I'll help!"
)

NOT_CONFIGURED_REPLY = (
    "The AI brain isn't configured yet. Add a Groq API key to `.env` "
    "(`GROQ_API_KEY=gsk_...`) and restart the server."
)


class EduSession:
    def __init__(self) -> None:
        self.history: list[dict[str, str]] = []


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

        analysis = self.llm.analyze(text, session.history)

        if not analysis.get("is_education", True):
            return {
                "reply": OFF_TOPIC_REPLY,
                "intent": "off_topic",
                "intents": analysis.get("intents"),
                "role": analysis.get("user_role"),
                "context": {},
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

        # Deterministically force a live search for any institution or factual
        # query (so worldwide colleges/universities/schools always get real,
        # source-cited links, including official websites).
        institution = (analysis.get("institution") or "").strip()
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
