"""Constituent colleges and parent universities for grounded answers."""

from __future__ import annotations

# Alias (lowercase) -> canonical institution name used in orchestrator / official_links.
CONSTITUENT_ALIASES: dict[str, str] = {
    "srki": "Shree Ramkrishna Institute of Computer Education and Applied Sciences",
    "shree ramkrishna": "Shree Ramkrishna Institute of Computer Education and Applied Sciences",
    "ramkrishna institute": "Shree Ramkrishna Institute of Computer Education and Applied Sciences",
    "sarvajanik university": "Sarvajanik University",
    "sarvajanik": "Sarvajanik University",
    "su surat": "Sarvajanik University",
    "su": "Sarvajanik University",
    "vnsgu": "Veer Narmad South Gujarat University",
    "veer narmad": "Veer Narmad South Gujarat University",
    "south gujarat university": "Veer Narmad South Gujarat University",
    "gtu": "Gujarat Technological University",
    "svnit": "Sardar Vallabhbhai National Institute of Technology Surat",
}

# Parent university for constituent colleges (for context in answers).
PARENT_UNIVERSITY: dict[str, str] = {
    "Shree Ramkrishna Institute of Computer Education and Applied Sciences": "Sarvajanik University",
}

# Named constituent / affiliated colleges -> canonical name (expand via web + official parent site).
VNSGU_AFFILIATED_ALIASES: dict[str, str] = {
    "government engineering college surat": "Veer Narmad South Gujarat University",
    "gec surat": "Veer Narmad South Gujarat University",
    "bhagwan mahavir college": "Veer Narmad South Gujarat University",
    "bcp": "Veer Narmad South Gujarat University",
    "bharatiya vidya bhavan": "Veer Narmad South Gujarat University",
}

SU_CONSTITUENT_ALIASES: dict[str, str] = {
    "srki": "Shree Ramkrishna Institute of Computer Education and Applied Sciences",
    "shree ramkrishna institute": "Shree Ramkrishna Institute of Computer Education and Applied Sciences",
}


def resolve_constituent(query: str) -> str | None:
    """Match constituent college / university short names in a query."""
    low = query.lower()
    for alias, canonical in {**CONSTITUENT_ALIASES, **VNSGU_AFFILIATED_ALIASES, **SU_CONSTITUENT_ALIASES}.items():
        if len(alias) < 3:
            continue
        if alias in low:
            return canonical
    return None
