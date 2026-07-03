"""Optional local SRKI curriculum dataset for education-mode grounding."""

from __future__ import annotations

from typing import Any

from backend.app.config import settings


def try_local_curriculum_block(
    query: str,
    institution: str,
    resolved: dict[str, str],
) -> tuple[str | None, dict[str, Any] | None]:
    """Return markdown + metadata when SRKI JSON curriculum data is available."""
    if not institution:
        return None, None
    low = institution.lower()
    if "srki" not in low and "ramkrishna" not in low:
        return None, None
    try:
        from backend.app.pipeline.curriculum_store import CurriculumStore

        store = CurriculumStore()
        if not store.entries:
            return None, None
        text = store.answer(query, resolved, {})
        if not text:
            return None, None
        meta = {
            "type": "local_dataset",
            "name": "SRKI curriculum JSON",
            "entries": len(store.entries),
            "path": str(settings.srki_json_data_dir or ""),
        }
        block = (
            f"[LOCAL-DATASET] SRKI official curriculum data ({len(store.entries)} semester files)\n"
            f"{text}\n"
            f"Source: SRKI local curriculum dataset"
        )
        return block, meta
    except Exception:
        return None, None
