import re
from typing import Any

DISAMBIGUATION_MAP: dict[str, list[dict[str, str]]] = {
    "cs": [
        {"resolution": "Computer Science", "label": "Computer Science (academic)"},
        {"resolution": "Communication Skills", "label": "Communication Skills (academic)"},
    ],
    "bt": [{"resolution": "Biotechnology", "label": "Biotechnology"}],
    "mb": [{"resolution": "Microbiology", "label": "Microbiology"}],
    "it": [{"resolution": "Information Technology", "label": "Information Technology"}],
}


def find_ambiguous_terms(query: str, resolved: dict[str, str]) -> dict[str, list[dict[str, str]]]:
    needed: dict[str, list[dict[str, str]]] = {}
    lower = query.lower()
    for term, options in DISAMBIGUATION_MAP.items():
        if term in resolved:
            continue
        pattern = rf"\b{re.escape(term)}\b"
        if re.search(pattern, lower) and len(options) > 1:
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
    for term, value in resolved.items():
        out = re.sub(rf"\b{re.escape(term)}\b", value, out, flags=re.IGNORECASE)
    return out
