"""Write baseline validation report for core SRKI queries."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.pipeline import web_scraper  # noqa: E402
from backend.app.pipeline.orchestrator import HybridOrchestrator  # noqa: E402

VALIDATION_QUERIES = [
    ("Hello..", "greeting"),
    ("what is about CS ?", "disambiguation"),
    ("Computer Science", "course_overview"),
    ("How can I apply for admission 2026-27?", "admission"),
    ("What is the fee structure at SRKI?", "fees"),
    ("will you give me sem-3 course details of MB ?", "syllabus"),
    ("What is the contact phone and email for SRKI?", "contact"),
    ("What courses are offered at SRKI?", "courses_list"),
]


def main() -> None:
    out_dir = ROOT / "data" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    orch = HybridOrchestrator()
    rows = []
    for message, category in VALIDATION_QUERIES:
        result = orch.chat(f"val-{category}", message)
        rows.append(
            {
                "category": category,
                "message": message,
                "intent": result.get("intent"),
                "source": result.get("source"),
                "needs_clarification": result.get("needs_clarification", False),
                "reply_preview": (result.get("reply") or "")[:300],
            }
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "health": {
            "curriculum_files": len(orch.curriculum.entries),
            "web_cache_pages": orch.web.page_count,
            "web_cache_fresh": web_scraper.cache_is_fresh(),
        },
        "queries": rows,
    }
    path = out_dir / "validation_baseline.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Validation baseline written to {path}")
    for r in rows:
        print(f"  [{r['category']}] intent={r['intent']} source={r['source']}")


if __name__ == "__main__":
    main()
