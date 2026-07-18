import re
from typing import Any

DISAMBIGUATION_MAP: dict[str, list[dict[str, str]]] = {
    "cs": [
        {"resolution": "Computer Science", "label": "Computer Science (academic course / BSc CS)"},
        {"resolution": "Communication Skills", "label": "Communication Skills (subject / soft skills)"},
    ],
    "ca": [
        {"resolution": "Chartered Accountant", "label": "CA — Chartered Accountant (professional qualification)"},
        {"resolution": "Computer Applications", "label": "CA — Computer Applications (academic course / BCA stream)"},
        {"resolution": "Chartered Accountancy", "label": "CA — Chartered Accountancy exam & syllabus (education)"},
    ],
    "bt": [{"resolution": "Biotechnology", "label": "Biotechnology"}],
    "mb": [{"resolution": "Microbiology", "label": "Microbiology"}],
    "it": [{"resolution": "Information Technology", "label": "Information Technology"}],
}

# Patterns where "CS" clearly means Computer Science (degree/program), not Communication Skills.
_CS_COMPUTER_SCIENCE_HINTS = (
    r"\bb\.?\s*sc\.?\s*cs\b",
    r"\bbsccs\b",
    r"\bbsc\s*[-/]?\s*cs\b",
    r"\bm\.?\s*sc\.?\s*cs\b",
    r"\bmsc\s*[-/]?\s*cs\b",
    r"\bcs\s+(?:sem|semester|syllabus|course|program|programme|department|degree|honours|hons)\b",
    r"\b(?:sem|semester|syllabus|course|program|programme|department|degree)\s+cs\b",
    r"\bcomputer\s+science\b",
)


def _cs_means_computer_science(query: str) -> bool:
    low = query.lower()
    return any(re.search(p, low) for p in _CS_COMPUTER_SCIENCE_HINTS)


def reconcile_resolutions(query: str, resolved: dict[str, str]) -> None:
    """Allow switching to another meaning later (e.g. Communication Skills after CS)."""
    lower = query.lower()
    # Degree-style "BSc CS" always means Computer Science.
    if _cs_means_computer_science(query):
        resolved["cs"] = "Computer Science"
    for term, options in DISAMBIGUATION_MAP.items():
        if term not in resolved or len(options) <= 1:
            continue
        current = resolved[term].lower()
        for opt in options:
            alt = opt["resolution"].lower()
            if alt != current and alt in lower:
                resolved[term] = opt["resolution"]
                break
        # Re-ask when user repeats the bare abbreviation without a chosen meaning.
        if re.search(rf"\b{re.escape(term)}\b", lower):
            if not any(opt["resolution"].lower() in lower for opt in options):
                if any(w in lower for w in ("what", "about", "mean", "tell", "?")):
                    # Don't unset CS when query clearly means Computer Science.
                    if term == "cs" and _cs_means_computer_science(query):
                        continue
                    resolved.pop(term, None)


def find_ambiguous_terms(query: str, resolved: dict[str, str]) -> dict[str, list[dict[str, str]]]:
    needed: dict[str, list[dict[str, str]]] = {}
    lower = query.lower()
    # Auto-resolve CS → Computer Science for BSc CS / syllabus / semester queries.
    if "cs" not in resolved and _cs_means_computer_science(query):
        resolved["cs"] = "Computer Science"
    for term, options in DISAMBIGUATION_MAP.items():
        if term in resolved:
            continue
        pattern = rf"\b{re.escape(term)}\b"
        if re.search(pattern, lower) and len(options) > 1:
            # Skip CS clarification when context already implies Computer Science.
            if term == "cs" and _cs_means_computer_science(query):
                continue
            needed[term] = options
    return needed


def format_clarification(needed: dict[str, list[dict[str, str]]]) -> str:
    parts: list[str] = []
    for term, options in needed.items():
        lines = [f"When you mention '{term}', do you mean:"]
        for i, opt in enumerate(options, 1):
            lines.append(f"{i}. {opt['label']}")
        lines.append("Please specify which one you're referring to.")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def resolve_from_reply(reply: str, needed: dict[str, list[dict[str, str]]]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    text = reply.strip().lower()
    for term, options in needed.items():
        for opt in options:
            if opt["resolution"].lower() in text or opt["label"].lower() in text:
                resolved[term] = opt["resolution"]
                break
        if term not in resolved and text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(options):
                resolved[term] = options[idx]["resolution"]
    return resolved


def apply_resolutions(query: str, resolved: dict[str, str]) -> str:
    out = query
    # Prefer Computer Science for degree-style CS even if session has an older CS meaning.
    if _cs_means_computer_science(query):
        resolved["cs"] = "Computer Science"
    for term, value in resolved.items():
        out = re.sub(rf"\b{re.escape(term)}\b", value, out, flags=re.IGNORECASE)
    return out
