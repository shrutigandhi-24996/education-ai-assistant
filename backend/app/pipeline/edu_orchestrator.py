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

from typing import Any

from backend.app.config import settings
from backend.app.pipeline.llm_client import LLMClient
from backend.app.pipeline.preprocessing import preprocess
from backend.app.pipeline.web_search import search_with_grounding

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

    def _gather_web_context(self, queries: list[str]) -> tuple[str, list[str]]:
        blocks: list[str] = []
        sources: list[str] = []
        for q in queries[: settings.edu_search_max_queries]:
            payload = search_with_grounding(q)
            for r in (payload.get("results") or [])[:4]:
                url = r.get("url")
                body = (r.get("extract") or r.get("snippet") or "").strip()
                if not url or not body:
                    continue
                if len(body) > 700:
                    body = body[:700].rsplit(" ", 1)[0] + "…"
                blocks.append(f"[{r.get('title') or url}]\n{body}\nSource: {url}")
                if url not in sources:
                    sources.append(url)
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
                "source": "domain_guard",
            }

        clarification = analysis.get("clarification")
        if clarification:
            return {
                "reply": clarification,
                "intent": "clarification",
                "intents": analysis.get("intents"),
                "role": analysis.get("user_role"),
                "needs_clarification": True,
                "source": "clarification",
            }

        web_context, sources = "", []
        if analysis.get("needs_web_search") and analysis.get("search_queries"):
            web_context, sources = self._gather_web_context(analysis["search_queries"])

        reply = self.llm.generate(text, analysis, web_context, session.history)

        session.history.append({"role": "user", "content": text})
        session.history.append({"role": "assistant", "content": reply})
        max_msgs = settings.edu_history_turns * 2
        if len(session.history) > max_msgs:
            session.history = session.history[-max_msgs:]

        intents = analysis.get("intents") or []
        return {
            "reply": reply,
            "intent": intents[0] if intents else "general_query",
            "intents": intents,
            "is_multi_intent": analysis.get("is_multi_intent", len(intents) > 1),
            "role": analysis.get("user_role"),
            "confidence": 1.0,
            "sources": sources or None,
            "source": "llm+web" if sources else "llm",
        }
