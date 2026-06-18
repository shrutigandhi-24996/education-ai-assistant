"""Refresh scraped content from official SRKI websites."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import settings  # noqa: E402
from backend.app.pipeline import web_scraper  # noqa: E402


def main() -> None:
    print("Scraping official SRKI pages (this may take 1–2 minutes)...")
    n = web_scraper.refresh_cache_if_needed(force=True)
    print(f"Done. Indexed pages with content: {n}")
    print(f"Cache file: {settings.web_cache_dir / 'srki_web_cache.json'}")


if __name__ == "__main__":
    main()
