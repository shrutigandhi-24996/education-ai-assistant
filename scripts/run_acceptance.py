"""Run SRKI acceptance suite and write JSON report."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.pipeline.orchestrator import HybridOrchestrator  # noqa: E402
from tests.acceptance_cases import ACCEPTANCE_CASES  # noqa: E402

REPORT_DIR = ROOT / "data" / "reports"


def evaluate_case(orchestrator: HybridOrchestrator, case: dict) -> dict:
    sid = case["session_id"]
    for pre_sid, pre_msg in case.get("pre_messages", []):
        orchestrator.chat(pre_sid, pre_msg)

    result = orchestrator.chat(sid, case["message"])
    reply = result.get("reply") or ""
    reply_lower = reply.lower()
    failures: list[str] = []

    if case.get("expect_clarification") and not result.get("needs_clarification"):
        failures.append("expected needs_clarification=True")
    if case.get("expect_clarification") is False and result.get("needs_clarification"):
        failures.append("unexpected clarification")

    exp_intent = case.get("expect_intent")
    if exp_intent is not None and result.get("intent") != exp_intent:
        failures.append(f"intent: got {result.get('intent')}, want {exp_intent}")

    exp_source = case.get("expect_source")
    if exp_source and result.get("source") != exp_source:
        failures.append(f"source: got {result.get('source')}, want {exp_source}")

    prefix = case.get("expect_source_prefix")
    if prefix is not None and prefix and not str(result.get("source", "")).startswith(prefix):
        failures.append(f"source prefix: got {result.get('source')}, want startswith {prefix}")

    needles = case.get("reply_contains_any", [])
    if needles and not any(n.lower() in reply_lower for n in needles):
        failures.append(f"missing any of: {', '.join(needles)}")

    url_hint = case.get("expect_url_hint")
    if url_hint and url_hint.lower() not in reply_lower:
        failures.append(f"missing url hint in reply: {url_hint}")

    if "404-error" in reply_lower:
        failures.append("reply contains 404-error boilerplate")

    return {
        "id": case["id"],
        "message": case["message"],
        "passed": len(failures) == 0,
        "failures": failures,
        "intent": result.get("intent"),
        "source": result.get("source"),
        "reply_preview": reply[:220].replace("\n", " "),
    }


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    orchestrator = HybridOrchestrator()
    rows = [evaluate_case(orchestrator, c) for c in ACCEPTANCE_CASES]
    passed = sum(1 for r in rows if r["passed"])
    total = len(rows)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "total": total,
        "pass_rate": round(passed / total * 100, 1) if total else 0,
        "results": rows,
    }
    out = REPORT_DIR / "acceptance_latest.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Acceptance: {passed}/{total} passed ({report['pass_rate']}%)")
    print(f"Report: {out}")
    for r in rows:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['id']}")
        if r["failures"]:
            for f in r["failures"]:
                print(f"         - {f}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
