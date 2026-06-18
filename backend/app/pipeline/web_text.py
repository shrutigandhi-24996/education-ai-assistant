"""Clean boilerplate from scraped SRKI page text."""
from __future__ import annotations

import re

_BOILERPLATE_PATTERNS = [
    r"Shree Ramkrishna Institute of Computer Education and Applied Sciences",
    r"0261-2240170.*?7228018497",
    r"7228018496\s*info@srki\.ac\.in\s*Contact Us",
    r"Examination Timetable\s*Home",
    r"Admin-Office:.*?Principal:",
    r"#### Call Us.*?#### Email",
    r"### About US.*?### Students Zone",
]

_PAGE_HEADER_RE = re.compile(
    r"^[A-Za-z\s\-]+ - Shree Ramkrishna Institute of Computer Education and Applied Sciences\s*",
    re.I,
)


def clean_snippet(text: str, max_len: int = 650) -> str:
    out = text.strip()
    out = _PAGE_HEADER_RE.sub("", out)
    for pat in _BOILERPLATE_PATTERNS:
        out = re.sub(pat, " ", out, flags=re.I | re.DOTALL)
    out = re.sub(r"\s+", " ", out).strip()
    if len(out) > max_len:
        out = out[: max_len - 3] + "..."
    return out


def snippet_is_useful(text: str, min_unique_words: int = 12) -> bool:
    cleaned = clean_snippet(text, max_len=10000)
    words = {w for w in re.findall(r"[a-z0-9]+", cleaned.lower()) if len(w) > 2}
    if "404-error" in cleaned.lower() or cleaned.lower().startswith("oops"):
        return False
    return len(words) >= min_unique_words
