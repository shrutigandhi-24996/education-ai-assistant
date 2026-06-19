"""Groq LLM client for the general education assistant.

Groq exposes an OpenAI-compatible chat-completions API, so we call it with a
plain HTTP request (no heavy SDK). Two roles:

  * analyze()  -> structured JSON: education-domain check, intents (single/multi),
                 user role (multi-user), pragmatic context, and whether a live
                 web search is needed plus the search queries.
  * generate() -> the final grounded answer, instructed to use ONLY the provided
                 web context for specific facts (anti-hallucination).
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from backend.app.config import settings

ANALYZE_SYSTEM = """You are the analysis stage of an EDUCATION-DOMAIN assistant.
Return ONLY a JSON object (no prose) with this exact schema:
{
  "is_education": boolean,            // true if the query is about education: admissions, colleges/universities/schools, courses, scholarships, exams, departments, faculty, fees, results, career guidance, study abroad, etc.
  "topic": string,                   // short label of what the user wants
  "institution": string|null,        // the SPECIFIC named school/college/university the user asks about (e.g. "Harvard University", "VNSGU", "Delhi Public School"); null if none named
  "user_role": "student"|"parent"|"faculty"|"admin"|"counsellor"|"other",
  "intents": [string],               // one or MORE intent labels (multi-intent) e.g. ["admission_process","scholarship_info"]
  "is_multi_intent": boolean,
  "needs_web_search": boolean,       // true if up-to-date or institution-specific facts are needed
  "search_queries": [string],        // 1-3 focused web search queries; empty if not needed
  "clarification": string|null       // if the query is too ambiguous to answer, a short clarifying question; else null
}
CRITICAL RULES:
- Users often write SHORT NAMES or abbreviations (VNSGU, IIT, MIT, GTU, SRKI). The query may already contain the expanded full name after preprocessing — use that for "institution".
- If "institution" is a specific named school/college/university anywhere in the world, then "needs_web_search" MUST be true and "search_queries" MUST include one query for its OFFICIAL WEBSITE (e.g. "<institution> official website") plus one for the topic.
- General career guidance or 'how does X generally work' does NOT need web search.
- Be strict about is_education: greetings/thanks count as education-context true."""

GENERATE_SYSTEM = """You are an Education Assistant (like ChatGPT but focused ONLY on the education domain:
admissions, colleges & universities, courses, scholarships, exams, departments, faculty, fees, results,
and career guidance). You help students, parents, faculty and counsellors.

STYLE:
- Be clear, structured and friendly. Use short paragraphs, bullet points and headings where helpful.
- Tailor the tone to the user's role when known.
- Answer in the user's language if they wrote in another language.

ACCURACY / ANTI-HALLUCINATION (very important):
- For SPECIFIC facts (exact dates, fees, deadlines, cutoffs, contact details, a particular institution's
  rules), use ONLY the information in the provided WEB CONTEXT. Quote the relevant detail and cite the
  source link inline.
- If a specific fact is NOT in the WEB CONTEXT, say you don't have the verified detail and point the user
  to the official source. NEVER invent dates, fees, numbers, names, or links. Only use links that appear
  in the WEB CONTEXT (never make up URLs).
- You MAY give general guidance (how processes usually work, career advice, study tips) from your own
  knowledge, but clearly frame it as general guidance.

LINKS (always do this when WEB CONTEXT is present):
- If any source is tagged [OFFICIAL], show it first under an "🏛️ Official website" line with the full link.
- End every answer that used WEB CONTEXT with a "Sources" section listing the links you used (markdown links).
- For an institution (any college/university/school worldwide), always try to give at least one valid link,
  preferring the official website.

SCOPE: If the question is outside education, politely decline and steer back to education topics."""


class LLMClient:
    def __init__(self) -> None:
        self.api_key = settings.groq_api_key.strip()
        self.base_url = settings.groq_base_url.rstrip("/")

    @property
    def ready(self) -> bool:
        return bool(self.api_key)

    def _chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        json_mode: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model or settings.groq_model,
            "messages": messages,
            "temperature": settings.llm_temperature if temperature is None else temperature,
            "max_tokens": max_tokens or settings.llm_max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=settings.llm_request_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def analyze(self, message: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        msgs: list[dict[str, str]] = [{"role": "system", "content": ANALYZE_SYSTEM}]
        if history:
            msgs.extend(history[-settings.edu_history_turns :])
        msgs.append({"role": "user", "content": message})
        try:
            raw = self._chat(
                msgs,
                model=settings.groq_fast_model,
                json_mode=True,
                temperature=0.0,
                max_tokens=400,
            )
            data = json.loads(raw)
        except Exception:
            # Fail open: treat as education, no web search.
            return {
                "is_education": True,
                "topic": message[:60],
                "institution": None,
                "user_role": "student",
                "intents": ["general_query"],
                "is_multi_intent": False,
                "needs_web_search": False,
                "search_queries": [],
                "clarification": None,
            }
        data.setdefault("is_education", True)
        data.setdefault("institution", None)
        data.setdefault("intents", ["general_query"])
        data.setdefault("user_role", "student")
        data.setdefault("is_multi_intent", len(data.get("intents", [])) > 1)
        data.setdefault("needs_web_search", False)
        data.setdefault("search_queries", [])
        data.setdefault("clarification", None)
        return data

    def generate(
        self,
        message: str,
        analysis: dict[str, Any],
        web_context: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        role = analysis.get("user_role", "student")
        intents = ", ".join(analysis.get("intents", []) or [])
        context_block = web_context.strip() or "(no web context retrieved)"
        user_block = (
            f"User role: {role}\n"
            f"Detected intents: {intents}\n\n"
            f"WEB CONTEXT (use only this for specific facts; cite the links):\n{context_block}\n\n"
            f"User question: {message}"
        )
        msgs: list[dict[str, str]] = [{"role": "system", "content": GENERATE_SYSTEM}]
        if history:
            msgs.extend(history[-settings.edu_history_turns :])
        msgs.append({"role": "user", "content": user_block})
        return self._chat(msgs, model=settings.groq_model).strip()
