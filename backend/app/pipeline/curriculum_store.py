"""Load SRKI semester JSON curricula and format answers (no FAISS required)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from backend.app.config import settings

PROGRAM_SLUGS: dict[str, str] = {
    "cs": "Computer Science",
    "it": "Information Technology",
    "mb": "Microbiology",
    "bt": "Biotechnology",
    "biotech": "Biotechnology",
    "chemistry": "Chemistry",
    "wmt": "Web and Mobile Technology",
    "ac": "Advanced Computing",
    "genetics": "Genetics",
    "organic chemistry": "Organic Chemistry",
    "medical bt": "Medical Biotechnology",
    "clinical embryology": "Clinical Embryology",
}

PROGRAM_KEYWORDS: dict[str, str] = {
    "computer science": "cs",
    "information technology": "it",
    "microbiology": "mb",
    "biotechnology": "bt",
    "chemistry": "chemistry",
    "web and mobile": "wmt",
    "advanced computing": "ac",
    "genetics": "genetics",
    "organic chemistry": "organic chemistry",
    "medical biotechnology": "medical bt",
    "clinical embryology": "clinical embryology",
}


@dataclass
class CurriculumEntry:
    path: Path
    degree: str  # BSc or MSc
    program_slug: str
    semester: int
    program_name: str


class CurriculumStore:
    def __init__(self) -> None:
        self.entries: list[CurriculumEntry] = []
        self._index()

    def _index(self) -> None:
        data_dir = settings.srki_json_data_dir
        if not data_dir or not data_dir.exists():
            return
        for path in sorted(data_dir.glob("*.json")):
            entry = self._parse_filename(path)
            if entry:
                self.entries.append(entry)

    def _parse_filename(self, path: Path) -> CurriculumEntry | None:
        stem = path.stem.lower().replace("_", " ")
        degree = "MSc" if "m.sc" in stem or stem.startswith("m sc") else "BSc" if "b.sc" in stem else None
        if not degree:
            return None
        sem_match = re.search(r"sem(?:ester)?[- ]?(\d+)", stem)
        if not sem_match:
            return None
        semester = int(sem_match.group(1))
        core = stem.replace("m.sc", "").replace("b.sc", "").replace("m sc", "").replace("b sc", "")
        core = re.sub(r"sem(?:ester)?[- ]?\d+", "", core).strip(" -.")
        program_slug = core.strip()
        program_name = PROGRAM_SLUGS.get(program_slug, program_slug.title())
        return CurriculumEntry(path, degree, program_slug, semester, program_name)

    def resolve_program(self, text: str, resolved: dict[str, str], context: dict) -> str | None:
        lower = text.lower()
        for term, value in resolved.items():
            if term in PROGRAM_SLUGS or value:
                return value if len(value) > 2 else PROGRAM_SLUGS.get(term, value)
        courses = context.get("Course") or []
        if courses:
            return courses[0]
        for phrase, slug in PROGRAM_KEYWORDS.items():
            if phrase in lower:
                return PROGRAM_SLUGS.get(slug, phrase.title())
        for slug, name in PROGRAM_SLUGS.items():
            if re.search(rf"\b{re.escape(slug)}\b", lower):
                return name
        return None

    def resolve_semester(self, text: str, context: dict) -> int | None:
        if context.get("Semester"):
            return int(context["Semester"])
        lower = text.lower()
        m = re.search(r"sem(?:ester)?[- ]?(\d+)", lower)
        if m:
            return int(m.group(1))
        return None

    def resolve_degree(self, text: str) -> str | None:
        lower = text.lower()
        if "m.sc" in lower or "msc" in lower or "master" in lower:
            return "MSc"
        if "b.sc" in lower or "bsc" in lower or "bachelor" in lower:
            return "BSc"
        return None

    def find_entry(
        self, program_name: str | None, semester: int | None, degree: str | None
    ) -> CurriculumEntry | None:
        if not self.entries:
            return None
        slug_candidates = [
            k for k, v in PROGRAM_SLUGS.items() if v.lower() == (program_name or "").lower()
        ]
        if program_name:
            slug_candidates.append(program_name.lower())

        matches = []
        for e in self.entries:
            prog_ok = not program_name or (
                e.program_name.lower() == program_name.lower()
                or any(s in e.program_slug for s in slug_candidates)
                or program_name.lower() in e.program_name.lower()
            )
            sem_ok = semester is None or e.semester == semester
            deg_ok = degree is None or e.degree == degree
            if prog_ok and sem_ok and deg_ok:
                matches.append(e)
        if not matches:
            return None
        if degree is None and semester is not None:
            degree = "MSc" if semester <= 4 else "BSc"
        if degree:
            deg_matches = [m for m in matches if m.degree == degree]
            if deg_matches:
                matches = deg_matches
        if semester:
            sem_matches = [m for m in matches if m.semester == semester]
            if sem_matches:
                matches = sem_matches
        return matches[0]

    def load(self, entry: CurriculumEntry) -> dict:
        with open(entry.path, encoding="utf-8") as f:
            return json.load(f)

    def answer(self, query: str, resolved: dict[str, str], context: dict) -> str | None:
        program = self.resolve_program(query, resolved, context)
        semester = self.resolve_semester(query, context)
        degree = self.resolve_degree(query)

        if program and not semester:
            return self._program_overview(program, degree)

        if not program:
            return None

        entry = self.find_entry(program, semester, degree)
        if not entry and semester:
            entry = self.find_entry(program, semester, "MSc" if degree is None else degree)
        if not entry:
            return (
                f"I found **{program}** at SRKI but could not locate semester "
                f"{semester or '?'} in the curriculum files. "
                "Try specifying BSc or MSc (e.g. 'MSc Microbiology sem-3')."
            )
        data = self.load(entry)
        return format_curriculum_markdown(data, entry)

    def _program_overview(self, program: str, degree: str | None) -> str:
        degree_line = (
            f"The college offers both Bachelor's (BSc) and Master's (MSc) tracks in {program}."
            if not degree
            else f"Here is an overview of the {degree} track in {program}."
        )
        entries = [e for e in self.entries if program.lower() in e.program_name.lower()]
        sems = sorted({e.semester for e in entries})
        sem_list = ", ".join(str(s) for s in sems[:8]) if sems else "1–6 (BSc) or 1–4 (MSc)"
        return f"""# {program} Program at SRKI

## PROGRAM OVERVIEW
{degree_line}
The {program} program at SRKI focuses on strong theory, practical labs, and industry-aligned skills.

## AVAILABLE SEMESTERS (in knowledge base)
Semesters with detailed syllabus data: {sem_list}.

Ask for a specific semester, for example:
"sem-3 course details of {program.split()[0][:2].upper() if program else 'MB'}" or "BSc {program} semester 1"."""


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    if len(title) > 120:
        title = title[:117] + "..."
    return title


def format_curriculum_markdown(data: dict, entry: CurriculumEntry) -> str:
    program = data.get("program") or entry.program_name
    semester = data.get("semester") or entry.semester
    institute = data.get("institute", "SRKI, Surat")
    courses = data.get("courses") or []

    lines = [
        f"# {program} Program at SRKI",
        "",
        "## PROGRAM OVERVIEW",
        f"The {program} program at {institute} includes structured theory, practicals, and assessments.",
        "",
        f"## {entry.degree} - Semester {semester}",
        "",
    ]

    for i, course in enumerate(courses[:12], 1):
        title = _clean_title(str(course.get("title", f"Course {i}")))
        ctype = course.get("type", "")
        credits = course.get("credits") or {}
        th = credits.get("theory", 0)
        pr = credits.get("practical", 0)
        lines.append(f"### {i}. {title}")
        if ctype:
            lines.append(f"- **Type:** {ctype}")
        if th or pr:
            lines.append(f"- **Credits:** Theory {th}, Practical {pr}")
        content = course.get("content") or {}
        if content:
            lines.append("- **Units:**")
            for unit_key in sorted(content.keys())[:4]:
                unit_text = str(content[unit_key])
                if len(unit_text) > 280:
                    unit_text = unit_text[:277] + "..."
                lines.append(f"  - {unit_key}: {unit_text}")
        lines.append("")

    if len(courses) > 12:
        lines.append(f"_…and {len(courses) - 12} more courses in this semester file._")
    return "\n".join(lines).strip()
