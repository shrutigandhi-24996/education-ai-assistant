"""Quick manual test for SRKI-only focus mode."""
import sys
import requests

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8001"
QUERIES = [
    "hi",
    "how to make pizza at home",
    "fees structure",
    "VNSGU BCA syllabus sem 1",
    "SRKI address",
]

for i, q in enumerate(QUERIES):
    r = requests.post(
        f"{BASE}/api/chat",
        json={"session_id": f"focus-test-{i}", "message": q, "user_id": "test@example.com"},
        timeout=120,
    )
    data = r.json()
    print("=" * 70)
    print("Q:", q)
    print("intent:", data.get("intent"), "| source:", data.get("source"))
    print((data.get("reply") or "")[:600])
    print()
