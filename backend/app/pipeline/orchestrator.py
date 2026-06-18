import re
from typing import Any

from backend.app.disambiguation import (
    apply_resolutions,
    find_ambiguous_terms,
    format_clarification,
    resolve_from_reply,
)
from backend.app.config import settings
from backend.app.pipeline.curriculum_store import CurriculumStore
from backend.app.pipeline.external_router import compose_external_answer, detect_external
from backend.app.pipeline.generator import GroundedGenerator
from backend.app.pipeline.intent import IntentClassifier
from backend.app.pipeline.preprocessing import preprocess
from backend.app.pipeline.rag import SrkiRetriever
from backend.app.pipeline.web_knowledge import WebKnowledge
from backend.app.pipeline.web_search import search_with_grounding

INTENT_TITLES: dict[str, str] = {
    "admission_query": "Admission",
    "fee_structure": "Fees",
    "course_info": "Courses",
    "exam_schedule": "Examinations",
    "result_query": "Results",
    "placement_info": "Placements",
    "faculty_info": "Faculty",
    "event_info": "Events",
    "infrastructure_info": "Campus & Facilities",
    "contact_info": "Contact",
}

WEB_FIRST_INTENTS = {
    "admission_query",
    "fee_structure",
    "contact_info",
    "placement_info",
    "event_info",
    "exam_schedule",
}

INTENT_FALLBACKS: dict[str, str] = {
    "placement_info": (
        "SRKI supports student career development through Sarvajanik University placement activities. "
        "For the latest placement drives, recruiters, and internship updates, contact the institute office "
        "at **7228018499 / 7228018500** or **info@srki.ac.in**, or visit the official website news section."
    ),
    "exam_schedule": (
        "Examination schedules and previous question papers are published on the SRKI website. "
        "Check the **Previous Question Paper** and **Examination Timetable** sections at srki.ac.in, "
        "or contact the academic office at **7228018497**."
    ),
    "fee_structure": (
        "Fee details are listed on the official **Fees Structure** page at srki.ac.in. "
        "For programme-wise fee confirmation, email **info@srki.ac.in** or call **7228018497**."
    ),
}

GREETING_RESPONSE = """I'm a college assistant that can answer questions about SRKI's courses, programs, and academic information. SRKI offers various courses and programs including:

- BSc and MSc in Computer Science
- BSc and MSc in Information Technology
- BSc and MSc in Microbiology
- BSc and MSc in Biotechnology
- BSc and MSc in Chemistry
- MSc in Web and Mobile Technologies
- MSc in Applied Chemistry

Ask me about admissions, fees, exams, faculty, placements, or semester-wise course details."""


class SessionState:
    def __init__(self) -> None:
        self.resolved_entities: dict[str, str] = {}
        self.pending_disambiguation: dict[str, list[dict[str, str]]] = {}
        self.context: dict[str, Any] = {}
        self.last_intent: str | None = None


class HybridOrchestrator:
    def __init__(self) -> None:
        self.intent_model = IntentClassifier()
        self.retriever = SrkiRetriever()
        self.curriculum = CurriculumStore()
        self.web = WebKnowledge()
        self.generator = GroundedGenerator()
        if settings.web_scrape_enabled:
            try:
                self.web.ensure_cache()
            except Exception:
                pass
        self.sessions: dict[str, SessionState] = {}

    def get_session(self, session_id: str) -> SessionState:
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState()
        return self.sessions[session_id]

    def chat(self, session_id: str, message: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        text = preprocess(message)

        if session.pending_disambiguation:
            resolved = resolve_from_reply(text, session.pending_disambiguation)
            session.resolved_entities.update(resolved)
            session.pending_disambiguation = {}
            if not resolved:
                return {
                    "reply": format_clarification(
                        find_ambiguous_terms(text, session.resolved_entities)
                    )
                    or "Please pick one of the numbered options so I can continue.",
                    "intent": session.last_intent,
                    "needs_clarification": True,
                }
            text = apply_resolutions(text, session.resolved_entities)

        ambiguous = find_ambiguous_terms(text, session.resolved_entities)
        if ambiguous:
            session.pending_disambiguation = ambiguous
            return {
                "reply": format_clarification(ambiguous),
                "intent": None,
                "needs_clarification": True,
            }

        text = apply_resolutions(text, session.resolved_entities)
        self._update_context(text, session, session.resolved_entities)

        intents = self.intent_model.predict_multi(text)
        primary_intent, primary_conf = intents[0]
        session.last_intent = primary_intent

        if primary_intent == "general_greeting" and self._is_greeting(text):
            return {
                "reply": GREETING_RESPONSE,
                "intent": primary_intent,
                "confidence": primary_conf,
                "context": session.context,
                "source": "greeting",
            }

        # External institution (VNSGU etc.) -> grounded web search, not SRKI data.
        external = detect_external(text)
        if external:
            ext = compose_external_answer(text, primary_intent, external["institution"])
            if ext:
                return {
                    "reply": ext["reply"],
                    "intent": primary_intent if primary_intent != "unknown" else "external_query",
                    "confidence": primary_conf,
                    "context": session.context,
                    "sources": ext.get("sources"),
                    "source": "external_web",
                }

        # Multi-intent: answer each detected intent and merge into one reply.
        if len(intents) > 1:
            return self._answer_multi(text, intents, session)

        return self._answer_single(text, primary_intent, primary_conf, session)

    def _answer_multi(
        self, text: str, intents: list[tuple[str, float]], session: SessionState
    ) -> dict[str, Any]:
        sub_queries = self._split_query(text, len(intents))
        sections: list[str] = []
        used_sources: list[str] = []
        for i, (intent, conf) in enumerate(intents):
            sub_text = sub_queries[i] if i < len(sub_queries) else text
            part = self._answer_single(sub_text, intent, conf, session)
            title = INTENT_TITLES.get(intent, intent.replace("_", " ").title())
            sections.append(f"### {title}\n{part['reply']}")
            used_sources.append(part.get("source", "fallback"))
        merged = (
            f"You asked about **{len(intents)} topics**. Here is each one:\n\n"
            + "\n\n".join(sections)
        )
        return {
            "reply": merged,
            "intent": "multi_intent",
            "intents": [i for i, _ in intents],
            "confidence": intents[0][1],
            "context": session.context,
            "source": "multi-intent",
            "component_sources": used_sources,
        }

    def _split_query(self, text: str, n: int) -> list[str]:
        parts = re.split(r"\?|\band\b|\balso\b|[,;]", text, flags=re.I)
        parts = [p.strip() for p in parts if p.strip()]
        return parts if parts else [text]

    def _answer_single(
        self, text: str, intent: str, confidence: float, session: SessionState
    ) -> dict[str, Any]:
        if intent in WEB_FIRST_INTENTS:
            web_reply = self.web.compose_answer(text, intent=intent, context=session.context)
            if web_reply and self._web_reply_valid(intent, web_reply):
                return {
                    "reply": web_reply,
                    "intent": intent,
                    "confidence": confidence,
                    "context": session.context,
                    "source": "web",
                }
            if intent in INTENT_FALLBACKS:
                return {
                    "reply": INTENT_FALLBACKS[intent],
                    "intent": intent,
                    "confidence": confidence,
                    "context": session.context,
                    "source": "intent_fallback",
                }

        curriculum_reply = self.curriculum.answer(
            text, session.resolved_entities, session.context
        )
        if not curriculum_reply and self._is_courses_list_query(text):
            excerpt = self.web._page_excerpt("courses-offered", text, max_len=1200)
            if excerpt:
                curriculum_reply = (
                    "## Courses Offered at SRKI\n\n"
                    f"{excerpt['chunk']}\n\n"
                    f"[Full list]({excerpt['url']})"
                )

        if curriculum_reply:
            enriched = self.web.enrich(curriculum_reply, text, intent="course_info")
            return {
                "reply": enriched,
                "intent": "course_info",
                "confidence": 1.0,
                "context": session.context,
                "source": "curriculum+web",
            }

        # Unseen / out-of-scope intent with no curriculum match: never fabricate
        # SRKI facts via the generic page composer. Search the web for a grounded
        # answer, else return a safe scoped message.
        if intent == "unknown":
            grounded_web = self._general_web_answer(text)
            if grounded_web:
                return {
                    "reply": grounded_web["reply"],
                    "intent": "unknown",
                    "confidence": confidence,
                    "context": session.context,
                    "sources": grounded_web.get("sources"),
                    "source": "web_search",
                }
            return {
                "reply": self._fallback(intent, session.context),
                "intent": "unknown",
                "confidence": confidence,
                "context": session.context,
                "source": "fallback",
            }

        web_reply = self.web.compose_answer(text, intent=intent, context=session.context)
        if web_reply and self._web_reply_valid(intent, web_reply):
            return {
                "reply": web_reply,
                "intent": intent,
                "confidence": confidence,
                "context": session.context,
                "source": "web",
            }

        hits = self.retriever.search(text, intent=intent, k=3)
        if hits:
            best = hits[0]
            answer = best.get("answer") or best.get("text", "")
            grounded = self._maybe_generate(text, hits)
            if grounded:
                answer = grounded
            answer = self.web.enrich(answer, text, intent=intent)
            return {
                "reply": answer,
                "intent": intent,
                "confidence": confidence,
                "context": session.context,
                "retrieval_score": best.get("score"),
                "source": "rag+web",
            }

        # Unseen / out-of-scope: try a grounded general web search before giving up.
        if intent == "unknown" or confidence < settings.intent_confidence_threshold:
            grounded_web = self._general_web_answer(text)
            if grounded_web:
                return {
                    "reply": grounded_web["reply"],
                    "intent": "unknown",
                    "confidence": confidence,
                    "context": session.context,
                    "sources": grounded_web.get("sources"),
                    "source": "web_search",
                }

        return {
            "reply": self._fallback(intent, session.context),
            "intent": intent,
            "confidence": confidence,
            "context": session.context,
            "source": "fallback",
        }

    def _maybe_generate(self, text: str, hits: list[dict]) -> str | None:
        """Optionally synthesize a grounded answer from retrieved hits."""
        if not (settings.use_generator and self.generator.ready):
            return None
        context = "\n\n".join(
            (h.get("answer") or h.get("text") or "") for h in hits[:3]
        ).strip()
        return self.generator.generate(text, context)

    def _general_web_answer(self, text: str) -> dict | None:
        """Grounded fallback for unseen queries: search the web, cite sources."""
        if not settings.external_search_enabled:
            return None
        payload = search_with_grounding(text)
        results = payload.get("results") or []
        if not results:
            return None
        lines = [
            "I don't have this in SRKI's verified data, but here is what I found "
            "on the web (please verify with official sources):",
            "",
        ]
        for i, r in enumerate(results[:3], start=1):
            body = (r.get("extract") or r.get("snippet") or "").strip()
            if len(body) > 300:
                body = body[:300].rsplit(" ", 1)[0] + "…"
            lines.append(f"**{i}. {r.get('title') or r.get('url')}**")
            if body:
                lines.append(body)
            lines.append(f"Source: [{r.get('url')}]({r.get('url')})")
            lines.append("")
        return {"reply": "\n".join(lines).strip(), "sources": [r.get("url") for r in results[:3]]}

    def _is_courses_list_query(self, text: str) -> bool:
        lower = text.lower()
        return "course" in lower and ("offer" in lower or "provide" in lower or "available" in lower)

    def _web_reply_valid(self, intent: str, reply: str) -> bool:
        lower = reply.lower()
        checks: dict[str, list[str]] = {
            "placement_info": ["placement", "recruiter", "career", "722801849"],
            "fee_structure": ["fee", "fees", "structure"],
            "exam_schedule": ["exam", "timetable", "schedule", "paper"],
            "contact_info": ["info@srki.ac.in", "722801849", "contact"],
        }
        required = checks.get(intent)
        if not required:
            return True
        return any(k.lower() in lower for k in required)

    def _is_greeting(self, text: str) -> bool:
        t = text.lower().strip(" .!")
        return t in {"hello", "hi", "hey", "hello..", "good morning", "good afternoon"}

    def _update_context(
        self, text: str, session: SessionState, resolved: dict[str, str] | None = None
    ) -> None:
        ctx = session.context
        course_aliases = {
            "computer science": "Computer Science",
            "information technology": "Information Technology",
            "microbiology": "Microbiology",
            "biotechnology": "Biotechnology",
            "chemistry": "Chemistry",
            "communication skills": "Communication Skills",
        }
        abbrev = {
            "mb": "Microbiology",
            "bt": "Biotechnology",
            "it": "Information Technology",
            "cs": "Computer Science",
        }
        lower = text.lower()
        for key, name in course_aliases.items():
            if key in lower:
                ctx.setdefault("Course", [])
                if name not in ctx["Course"]:
                    ctx["Course"].append(name)
        for abbr, name in abbrev.items():
            if re.search(rf"\b{re.escape(abbr)}\b", lower):
                ctx.setdefault("Course", [])
                if name not in ctx["Course"]:
                    ctx["Course"].append(name)
        if resolved:
            for value in resolved.values():
                ctx.setdefault("Course", [])
                if value not in ctx["Course"]:
                    ctx["Course"].append(value)
        sem = re.search(r"sem(?:ester)?[- ]?(\d+)", lower)
        if sem:
            ctx["Semester"] = int(sem.group(1))

    def _fallback(self, intent: str, context: dict[str, Any]) -> str:
        course = (context.get("Course") or [None])[0]
        if intent == "course_info" and course:
            return (
                f"I understand you're asking about **{course}** at SRKI. "
                "Run `python scripts/build_rag_index.py` to load full program details, "
                "or ask a more specific question (e.g. sem-3 course details of Microbiology)."
            )
        return (
            "I'm the SRKI College Course Assistant. I can help with admissions, fees, "
            "courses, exams, and campus information. Try asking about a specific program or semester."
        )
