import re

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", re.IGNORECASE)
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def is_valid_user_email(user_id: str) -> bool:
    value = (user_id or "").strip().lower()
    if not value or value == "anonymous":
        return False
    if UUID_RE.match(value):
        return False
    return bool(EMAIL_RE.match(value))
