"""Manual test: multi-intent queries answer every intent with its own section."""
import sys
import requests

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8001"
QUERIES = [
    "What is the admission process and fees structure for BSc CS at SRKI?",
    "Give me SRKI's fees structure and contact details",
]

for i, q in enumerate(QUERIES):
    r = requests.post(
        f"{BASE}/api/chat",
        json={"session_id": f"multi-test-{i}", "message": q, "user_id": "test@example.com"},
        timeout=180,
    )
    data = r.json()
    print("=" * 70)
    print("Q:", q)
    print("intents:", data.get("intents"), "| multi:", data.get("is_multi_intent"))
    print("--- reply ---")
    print(data.get("reply") or "")
    print("--- resources ---")
    for res in data.get("resources") or []:
        print(f"  [{res.get('type')}] {res.get('title')} -> {res.get('url')}")
    print()
