"""Merge SRKI datasets and export train/val splits for intent training."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import settings  # noqa: E402

OUT = ROOT / "data" / "processed"


def load_json(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows_a = load_json(settings.srki_dataset_a)
    rows_b = load_json(settings.srki_dataset_b)

    records: list[dict] = []
    seen_ids: set[str] = set()
    for source, rows in [("A", rows_a), ("B", rows_b)]:
        for row in rows:
            rid = f"{source}:{row.get('id', len(records))}"
            if rid in seen_ids:
                continue
            seen_ids.add(rid)
            records.append(
                {
                    "text": row["text"].strip(),
                    "intent": row["intent"],
                    "dialogue_act": row.get("dialogue_act"),
                    "context": row.get("context") or {},
                    "ideal_response": row.get("ideal_response"),
                }
            )
    split = int(len(records) * 0.9)
    train, val = records[:split], records[split:]

    for name, data in [("train", train), ("val", val), ("all", records)]:
        path = OUT / f"srki_{name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Wrote {path} ({len(data)} rows)")

    intents = sorted({r["intent"] for r in records})
    with open(OUT / "label_map.json", "w", encoding="utf-8") as f:
        json.dump({"labels": intents}, f, indent=2)
    print(f"Intents ({len(intents)}):", intents)


if __name__ == "__main__":
    main()
