"""Resolve short names / abbreviations for schools, colleges and universities.

Handles:
  * Unambiguous aliases  -> auto-expand (VNSGU, SRKI, IIT Bombay, …)
  * Homograph abbreviations (same short form, different institutions)
    -> ask the user to pick from numbered suggestions
  * Pragmatic resolution from conversation history or prior user choices
"""
from __future__ import annotations

import re
from typing import Any

# Same abbreviation, multiple institutions (homographs / polyseme abbreviations).
INSTITUTION_HOMOGRAPHS: dict[str, list[dict[str, str]]] = {
    "mit": [
        {
            "resolution": "Massachusetts Institute of Technology",
            "label": "MIT — Massachusetts Institute of Technology (USA)",
        },
        {
            "resolution": "Manipal Institute of Technology",
            "label": "MIT — Manipal Institute of Technology (India)",
        },
        {
            "resolution": "Madras Institute of Technology",
            "label": "MIT — Madras Institute of Technology, Anna University (India)",
        },
    ],
    "du": [
        {"resolution": "University of Delhi", "label": "DU — University of Delhi (India)"},
        {"resolution": "Durham University", "label": "DU — Durham University (UK)"},
    ],
    "pu": [
        {"resolution": "Savitribai Phule Pune University", "label": "PU — Savitribai Phule Pune University (India)"},
        {"resolution": "Panjab University", "label": "PU — Panjab University, Chandigarh (India)"},
        {"resolution": "Punjabi University", "label": "PU — Punjabi University, Patiala (India)"},
    ],
    "au": [
        {"resolution": "Andhra University", "label": "AU — Andhra University (India)"},
        {"resolution": "Anna University", "label": "AU — Anna University, Chennai (India)"},
        {"resolution": "Auro University", "label": "AU — Auro University, Surat (India)"},
    ],
    "gu": [
        {"resolution": "Gujarat University", "label": "GU — Gujarat University, Ahmedabad (India)"},
        {"resolution": "Goa University", "label": "GU — Goa University (India)"},
    ],
    "msu": [
        {
            "resolution": "Maharaja Sayajirao University of Baroda",
            "label": "MSU — Maharaja Sayajirao University of Baroda (India)",
        },
        {"resolution": "Michigan State University", "label": "MSU — Michigan State University (USA)"},
    ],
    "bu": [
        {"resolution": "Bangalore University", "label": "BU — Bangalore University (India)"},
        {"resolution": "Banaras Hindu University", "label": "BU — often BHU; Banaras Hindu University (India)"},
    ],
    "su": [
        {"resolution": "Sarvajanik University", "label": "SU — Sarvajanik University, Surat (India)"},
        {"resolution": "Syracuse University", "label": "SU — Syracuse University (USA)"},
        {"resolution": "Stanford University", "label": "SU — Stanford University (USA) [less common abbreviation]"},
    ],
    "gtu": [
        {
            "resolution": "Gujarat Technological University",
            "label": "GTU — Gujarat Technological University (Ahmedabad, India)",
        },
    ],
    "iit": [
        {"resolution": "Indian Institute of Technology Bombay", "label": "IIT — IIT Bombay (India)"},
        {"resolution": "Indian Institute of Technology Delhi", "label": "IIT — IIT Delhi (India)"},
        {"resolution": "Indian Institute of Technology Madras", "label": "IIT — IIT Madras (India)"},
        {"resolution": "Indian Institute of Technology Kanpur", "label": "IIT — IIT Kanpur (India)"},
        {"resolution": "Indian Institute of Technology Kharagpur", "label": "IIT — IIT Kharagpur (India)"},
    ],
    "nit": [
        {"resolution": "Sardar Vallabhbhai National Institute of Technology Surat", "label": "NIT — SVNIT Surat (India)"},
        {"resolution": "National Institute of Technology Trichy", "label": "NIT — NIT Trichy (India)"},
        {"resolution": "National Institute of Technology Karnataka", "label": "NIT — NIT Karnataka, Surathkal (India)"},
        {"resolution": "National Institute of Technology Warangal", "label": "NIT — NIT Warangal (India)"},
    ],
    "iiit": [
        {"resolution": "Indian Institute of Information Technology Allahabad", "label": "IIIT — IIIT Allahabad (India)"},
        {"resolution": "International Institute of Information Technology Hyderabad", "label": "IIIT — IIIT Hyderabad (India)"},
        {"resolution": "Indian Institute of Information Technology Bangalore", "label": "IIIT — IIIT Bangalore (India)"},
    ],
}

# Unambiguous short names -> canonical full institution name (auto-expanded).
INSTITUTION_ALIASES: dict[str, str] = {
    "vnsgu": "Veer Narmad South Gujarat University",
    "veer narmad": "Veer Narmad South Gujarat University",
    "veer narmad south gujarat university": "Veer Narmad South Gujarat University",
    "south gujarat university": "Veer Narmad South Gujarat University",
    "srki": "Shree Ramkrishna Institute of Computer Education and Applied Sciences",
    "shree ramkrishna": "Shree Ramkrishna Institute of Computer Education and Applied Sciences",
    "ramkrishna institute": "Shree Ramkrishna Institute of Computer Education and Applied Sciences",
    "sarvajanik university": "Sarvajanik University",
    "sarvajanik": "Sarvajanik University",
    "su surat": "Sarvajanik University",
    "scet surat": "Sarvajanik College of Engineering and Technology",
    "scet": "Sarvajanik College of Engineering and Technology",
    "brcm": "B.R.C.M. College of Business Administration",
    "srlim": "Smt. Shardarani Rameshchander Luthra Institute of Management",
    "scopa": "Shri Pankaj Kapadia Sarvajanik College of Performing Arts",
    "scol": "Sarvajanik College of Law",
    "sccca": "KP Human Sarvajanik College of Commerce and Computer Applications",
    "idpt": "MITRAJ Sarvajanik Institute of Design, Planning and Technology",
    "sctcc": "Sarvajanik Centre for Training and Certificate Courses",
    "scla": "Sarvajanik College of Liberal Arts",
    "mitraj": "MITRAJ Sarvajanik Institute of Design, Planning and Technology",
    "svnit": "Sardar Vallabhbhai National Institute of Technology Surat",
    "nit surat": "Sardar Vallabhbhai National Institute of Technology Surat",
    "jnu": "Jawaharlal Nehru University",
    "bhu": "Banaras Hindu University",
    "iitb": "Indian Institute of Technology Bombay",
    "iitd": "Indian Institute of Technology Delhi",
    "iitm": "Indian Institute of Technology Madras",
    "iit bombay": "Indian Institute of Technology Bombay",
    "iit delhi": "Indian Institute of Technology Delhi",
    "iit madras": "Indian Institute of Technology Madras",
    "iit kanpur": "Indian Institute of Technology Kanpur",
    "iit kharagpur": "Indian Institute of Technology Kharagpur",
    "harvard": "Harvard University",
    "stanford": "Stanford University",
    "oxford": "University of Oxford",
    "cambridge": "University of Cambridge",
    "mit usa": "Massachusetts Institute of Technology",
    "manipal": "Manipal Institute of Technology",
    "gtu ahmedabad": "Gujarat Technological University",
    "gtu": "Gujarat Technological University",
    "gujarat technological": "Gujarat Technological University",
    "gujarat university": "Gujarat University",
    "delhi university": "University of Delhi",
    "du delhi": "University of Delhi",
    "pune university": "Savitribai Phule Pune University",
    "sppu": "Savitribai Phule Pune University",
    "anna university": "Anna University",
    "auro university": "Auro University",
    "uka tarsadia": "Uka Tarsadia University",
    "msu baroda": "Maharaja Sayajirao University of Baroda",
    "ms university": "Maharaja Sayajirao University of Baroda",
    "aiims": "All India Institute of Medical Sciences",
    "bits pilani": "Birla Institute of Technology and Science Pilani",
    "bits": "Birla Institute of Technology and Science Pilani",
}

# Longer aliases first so "iit bombay" matches before "iit".
_SORTED_ALIASES = sorted(INSTITUTION_ALIASES.items(), key=lambda x: len(x[0]), reverse=True)

# Tokens that look like institution abbreviations (2–6 letters, optional digits).
_ABBR_TOKEN = re.compile(r"\b([a-z]{2,6}\d?)\b", re.I)


def _token_in_query(term: str, query: str) -> bool:
    return bool(re.search(rf"\b{re.escape(term)}\b", query, re.I))


def _query_specifies_option(query: str, options: list[dict[str, str]]) -> bool:
    """True when the query already names one homograph option (e.g. 'iit bombay')."""
    lower = query.lower()
    for opt in options:
        res = opt["resolution"].lower()
        for alias, full in _SORTED_ALIASES:
            if full.lower() == res and alias in lower:
                return True
        for token in res.split():
            if len(token) > 4 and token in lower:
                return True
    return False


def find_ambiguous_institutions(
    query: str, resolved: dict[str, str]
) -> dict[str, list[dict[str, str]]]:
    """Return homograph abbreviations in the query that still need clarification."""
    needed: dict[str, list[dict[str, str]]] = {}
    lower = query.lower()
    for term, options in INSTITUTION_HOMOGRAPHS.items():
        if term in resolved or len(options) <= 1:
            continue
        if not _token_in_query(term, lower):
            continue
        if _query_specifies_option(query, options):
            continue
        needed[term] = options
    return needed


def resolve_from_history(
    term: str,
    history: list[dict[str, str]],
    resolved: dict[str, str],
    last_institution: str | None,
) -> str | None:
    """Use prior turns to pick the institution when the same abbreviation was used before."""
    if term in resolved:
        return resolved[term]

    options = INSTITUTION_HOMOGRAPHS.get(term, [])
    if not options:
        return None

    # Recent explicit institution in session.
    if last_institution:
        low = last_institution.lower()
        for opt in options:
            if opt["resolution"].lower() in low or low in opt["resolution"].lower():
                return opt["resolution"]

    # Scan conversation history (newest first).
    for msg in reversed(history):
        content = (msg.get("content") or "").lower()
        for opt in options:
            res = opt["resolution"].lower()
            if res in content or any(w in content for w in res.split()[:3]):
                return opt["resolution"]

    return None


def format_institution_clarification(needed: dict[str, list[dict[str, str]]]) -> str:
    parts: list[str] = []
    for term, options in needed.items():
        lines = [
            f"The abbreviation **'{term.upper()}'** can refer to more than one institution. "
            f"Which one do you mean?"
        ]
        for i, opt in enumerate(options, 1):
            lines.append(f"{i}. {opt['label']}")
        lines.append("Reply with the **number** or the **full name** of your choice.")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def resolve_institution_from_reply(
    reply: str, needed: dict[str, list[dict[str, str]]]
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    text = reply.strip().lower()
    for term, options in needed.items():
        for opt in options:
            res_low = opt["resolution"].lower()
            label_low = opt["label"].lower()
            # Match full name, distinctive words, or label fragment.
            if res_low in text or any(w in text for w in res_low.split() if len(w) > 4):
                resolved[term] = opt["resolution"]
                break
            if label_low.split("—")[-1].strip()[:20] in text:
                resolved[term] = opt["resolution"]
                break
        if term not in resolved and re.fullmatch(r"\d+", text):
            idx = int(text) - 1
            if 0 <= idx < len(options):
                resolved[term] = options[idx]["resolution"]
        if term not in resolved:
            # "option 2", "number 2", "2nd"
            m = re.search(r"\b(\d+)\b", text)
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(options):
                    resolved[term] = options[idx]["resolution"]
    return resolved


def expand_institution_aliases(query: str, resolved: dict[str, str]) -> str:
    """Replace known short names with full institution names in the query."""
    out = query
    # User-confirmed homograph resolutions.
    for term, full in resolved.items():
        out = re.sub(rf"\b{re.escape(term)}\b", full, out, flags=re.I)
    # Longest unambiguous alias matches first.
    lower = out.lower()
    for alias, full in _SORTED_ALIASES:
        if alias in resolved.values():
            continue
        if alias in lower:
            out = re.sub(re.escape(alias), full, out, flags=re.I)
    return out


def detect_institution(query: str, resolved: dict[str, str]) -> str | None:
    """Best-effort canonical institution name from aliases + resolutions."""
    expanded = expand_institution_aliases(query, resolved)
    lower = expanded.lower()
    for alias, full in _SORTED_ALIASES:
        if alias in lower or full.lower() in lower:
            return full
    for term, full in resolved.items():
        if full.lower() in lower:
            return full
    return None
