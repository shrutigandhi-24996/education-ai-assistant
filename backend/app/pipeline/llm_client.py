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
import time
from typing import Any

import httpx

from backend.app.config import settings

RATE_LIMIT_FALLBACK_REPLY = (
    "I'm receiving a lot of questions right now and my AI brain hit a temporary rate limit. "
    "Please wait a few seconds and ask again — your question will be answered normally."
)

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
- If the user asks for institution-specific facts (admissions, fees, courses, scholarships, exams, contact, departments) but does NOT name which university/college/school, set "institution" to null, "needs_web_search" to false, and "clarification" to a short question asking which institution and what they want to know.
- General queries (top universities, career guidance, how to become X, comparisons) do NOT require a named institution — set clarification to null.
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

LINKS & OFFICIAL DOCUMENTS (always do this when WEB CONTEXT is present):
- WEB CONTEXT may include tags: [OFFICIAL-PDF], [OFFICIAL-DOC], [OFFICIAL-PAGE], [OFFICIAL-IMAGE], [OFFICIAL-PDF-CONTENT].
- When [OFFICIAL-PDF-CONTENT] is present, base specific facts (dates, fees, eligibility, syllabus, rules)
  primarily on that extracted PDF text. Quote the relevant lines briefly in your short answer.
- Syllabus PDFs may be found by navigating official site menus (Academics → Syllabus → course → semester).
  Use that content when present; if no PDF is available, answer from other official web context and say so clearly.
- The chat UI displays PDFs, documents, and informative images FIRST (above your text). Do NOT list PDF/file
  URLs or duplicate "Official PDFs & documents" sections in your reply — the user already sees them inline.
- NEVER invent PDF or file URLs.

ANSWER FORMAT:
- Answer ONLY the user's current question. Do NOT repeat or summarize answers from earlier chat turns.
- MULTI-INTENT questions (the user asks 2+ things at once, e.g. "admission process AND fees structure"):
  answer EVERY part, each under its own short bold heading (e.g. **Admission process** then **Fees structure**).
  Give each part a complete answer with its own official link(s). Never answer only one part.
- When PDFs, documents, or images are in WEB CONTEXT: keep the reply SHORT (2–5 sentences or a few tight bullets)
  with key facts from those sources. Skip long paragraphs and link lists.
- When no PDF/document/image applies: use clear, justified paragraphs with headings/bullets as needed.
- Contact/address/phone queries: answer ONLY with address/contact facts and the official contact link.
  Do NOT mention syllabus PDFs or unrelated campus/testimonial images for these questions.
- Admission queries: give the ACTUAL steps found in WEB CONTEXT, not just a link. For SRKI the process is:
  1) apply online at the Sarvajanik University admission portal (https://student.sarvajanikuniversity.ac.in:8080/admissionindex.html),
  2) provisional & final merit lists + admission schedule are published on the SRKI Admission Corner page
     (https://www.srki.ac.in/pages/admission-corner/),
  3) offline/lateral admission & other forms are on the SRKI Forms pages (application form PDF available).
  Mention eligibility/documents/dates ONLY if they appear in WEB CONTEXT.
- Fees queries: ALWAYS give these official links first:
  1) the official fees structure page (for SRKI: https://www.srki.ac.in/pages/fees-structure/)
  2) the embedded official fees PDF (for SRKI: https://www.srki.ac.in/upload/2025-26/Fee_Batch-2026.pdf)
  If [OFFICIAL-PDF-CONTENT] has amounts, briefly summarize key programme fees after the links.
  If amounts are unclear, still provide both links and tell the user to open the PDF — NEVER invent fee amounts
  and NEVER write placeholder text like "[amount unclear]" — simply omit the line and point to the PDF.
  Never write internal tags like [OFFICIAL-PDF-CONTENT] in the user-visible reply.
- Separate key facts from next steps briefly; avoid redundant source listings.

SYLLABUS ANSWERS (critical):
- When the user asks for a syllabus, structure the reply as: **Course & semester** → **Subjects/units/credits** (only from PDF/page content) → **Official PDF link**.
- Use ONLY subjects, units, and credits found in [OFFICIAL-PDF-CONTENT] or [OFFICIAL-PAGE-CONTENT]. Never invent subject names.
- If an [OFFICIAL-PDF] matches the requested course/semester, ALWAYS cite that PDF URL — never say the syllabus is unavailable when that PDF is in WEB CONTEXT.
- For SRKI BSc Microbiology / Biotechnology / Chemistry Sem-1, the official merged PDF is often
  https://www.srki.ac.in/upload/2023-24/syllabus/bt-ch-mb-sem1-merged.pdf (from the department page).
- If no PDF text is available but official syllabus pages/PDFs exist, say so clearly and give those official links.
- If BSc IT is requested but only a related CS syllabus PDF exists on the site, say that explicitly and still cite that official PDF.

SCOPE: If the question is outside education, politely decline and steer back to education topics.
CURRENT FOCUS: This deployment currently serves SRKI (Shree Ramkrishna Institute of Computer Education
and Applied Sciences, Surat) queries. When no institution is named, assume the user means SRKI.

PRIORITY INSTITUTIONS (SRKI, Sarvajanik University, VNSGU, GTU):
- SRKI = Shree Ramkrishna Institute of Computer Education and Applied Sciences (constituent of Sarvajanik University, Surat).
- SU = Sarvajanik University, Surat (parent of SRKI, SCET, SCOL, BRCM, SCCCA, SRLIM, SCOPA, SCTCC, IDPT, SCLA).
- VNSGU = Veer Narmad South Gujarat University, Surat.
- GTU = Gujarat Technological University. Official syllabus hub: https://gtu.ac.in/syllabus/syllabus.aspx (user selects course/semester there).
- When [OFFICIAL-SYLLABUS-PORTAL] is in WEB CONTEXT, tell the user to open that link FIRST to select/download the correct syllabus — do not invent subject lists if only the portal page is available.
- Use ONLY facts from WEB CONTEXT for these institutions. Never invent syllabus subjects, fees, dates, or PDF URLs.
- If WEB CONTEXT lacks verified facts, say so clearly and point to the official link provided — do NOT guess.
- When parent university and constituent college both appear, prefer the college named in the user's question.
- For SU constituent-college queries, mention the parent university only when relevant."""


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
            low = message.lower()
            inst_words = ("university", "college", "school", "institute", "vnsgu", "iit", "mit")
            fact_words = ("admission", "fee", "fees", "scholarship", "course", "department")
            needs_web = any(w in low for w in inst_words) or any(w in low for w in fact_words)
            return {
                "is_education": True,
                "topic": message[:60],
                "institution": None,
                "user_role": "student",
                "intents": ["general_query"],
                "is_multi_intent": False,
                "needs_web_search": needs_web,
                "search_queries": [message, f"{message} official website"] if needs_web else [],
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
        high_accuracy: bool = False,
        institution: str = "",
    ) -> str:
        role = analysis.get("user_role", "student")
        intents = ", ".join(analysis.get("intents", []) or [])
        context_block = web_context.strip() or "(no web context retrieved)"
        inst_line = (
            f"INSTITUTION FOR THIS QUESTION ONLY: {institution}\n"
            "Ignore data from any other college/university/school mentioned earlier in the chat.\n\n"
            if institution
            else ""
        )
        user_block = (
            f"{inst_line}"
            f"User role: {role}\n"
            f"Detected intents: {intents}\n\n"
            f"WEB CONTEXT (use only this for specific facts; cite the links):\n{context_block}\n\n"
            f"User question (answer THIS only — do not repeat prior answers): {message}"
        )
        msgs: list[dict[str, str]] = [{"role": "system", "content": GENERATE_SYSTEM}]
        if history:
            msgs.extend(history[-settings.edu_history_turns :])
        msgs.append({"role": "user", "content": user_block})
        if high_accuracy or is_syllabus_in_context(web_context):
            model = settings.groq_model
            max_tok = 700
        else:
            model = settings.groq_fast_model if settings.edu_fast_mode else settings.groq_model
            max_tok = 450 if settings.edu_fast_mode else settings.llm_max_tokens
        has_media = any(
            tag in (web_context or "").lower()
            for tag in ("[official-pdf", "[official-doc", "[official-image", "official-pdf-content")
        )
        if has_media and max_tok > 500:
            max_tok = 500
        try:
            return self._chat(msgs, model=model, max_tokens=max_tok).strip()
        except httpx.HTTPStatusError as exc:
            # Rate limit / transient upstream error: retry with the fast model and a
            # truncated context (fits smaller per-minute token budgets) instead of
            # crashing the whole request with a 500.
            if exc.response.status_code in (429, 500, 502, 503):
                short_block = (
                    f"{inst_line}"
                    f"User role: {role}\n"
                    f"Detected intents: {intents}\n\n"
                    f"WEB CONTEXT (use only this for specific facts; cite the links):\n"
                    f"{context_block[:4000]}\n\n"
                    f"User question (answer THIS only): {message}"
                )
                short_msgs = [
                    {"role": "system", "content": GENERATE_SYSTEM},
                    {"role": "user", "content": short_block},
                ]
                time.sleep(3)
                for alt in (settings.groq_fast_model, settings.groq_model):
                    if alt == model and alt != settings.groq_fast_model:
                        continue
                    try:
                        return self._chat(short_msgs, model=alt, max_tokens=450).strip()
                    except Exception:
                        time.sleep(3)
            return RATE_LIMIT_FALLBACK_REPLY
        except Exception:
            return RATE_LIMIT_FALLBACK_REPLY


def is_syllabus_in_context(web_context: str) -> bool:
    low = (web_context or "").lower()
    return "syllabus" in low or "official-pdf-content" in low
