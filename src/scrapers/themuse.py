"""
The Muse scraper.

The Muse exposes a public REST API that works without an API key for basic queries.
Endpoint: https://www.themuse.com/api/public/jobs

We filter for Computer & IT category and Internship level.
Optional API key raises rate limits — configured via THE_MUSE_API_KEY in .env.
"""

import time
from typing import List, Dict, Any

import requests
import structlog

from src.scrapers.base import BaseScraper
from src.utils.retry import retry_with_backoff
from src.config import settings

logger = structlog.get_logger()

BASE_URL = "https://www.themuse.com/api/public/jobs"
CATEGORIES = ["Computer and IT", "Data and Analytics", "Software Engineering"]
LEVEL = "Internship"


class TheMuseScraper(BaseScraper):
    source_name = "themuse"

    def _build_params(self, page: int, category: str) -> Dict:
        params = {
            "category": category,
            "level": LEVEL,
            "page": page,
            "descending": "true",
        }
        if settings.THE_MUSE_API_KEY:
            params["api_key"] = settings.THE_MUSE_API_KEY
        return params

    @retry_with_backoff(max_attempts=3)
    def _fetch_page(self, page: int, category: str) -> Dict:
        resp = requests.get(
            BASE_URL,
            params=self._build_params(page, category),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def fetch(self) -> List[Dict[str, Any]]:
        all_jobs: List[Dict] = []

        for category in CATEGORIES:
            page = 1
            while True:
                try:
                    data = self._fetch_page(page, category)
                    results = data.get("results") or []
                    if not results:
                        break
                    all_jobs.extend(results)

                    # Respect pagination limit
                    if page >= data.get("page_count", 1):
                        break
                    page += 1
                    time.sleep(0.5)

                except Exception as exc:
                    logger.warning(
                        "themuse_page_failed",
                        category=category,
                        page=page,
                        error=str(exc),
                    )
                    break

        logger.info("themuse_fetch_complete", total=len(all_jobs))
        return all_jobs

    def parse(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        # Company
        company_data = raw.get("company") or {}
        company = company_data.get("name") or "Unknown"

        # Location — The Muse returns a list of location objects
        locations = raw.get("locations") or []
        if locations:
            location = locations[0].get("name") or "Remote/Unknown"
        else:
            location = "Remote"

        # URL
        refs = raw.get("refs") or {}
        url = refs.get("landing_page") or ""

        # Tags from categories and levels
        categories = [c.get("name", "") for c in (raw.get("categories") or [])]
        levels = [l.get("name", "") for l in (raw.get("levels") or [])]
        tags = ["internship", "themuse"] + [t.lower() for t in categories + levels if t]

        # Publication date
        pub_date = (raw.get("publication_date") or "")[:10] or None

        return {
            "title": (raw.get("name") or "Software Intern")[:500],
            "company": company[:200],
            "location": location[:200],
            "url": url,
            "source": self.source_name,
            "posting_date": pub_date,
            "tags": tags[:20],
        }
