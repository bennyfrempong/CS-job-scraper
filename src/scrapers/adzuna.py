"""
Adzuna scraper.

Adzuna is a job aggregator with a public REST API.
Free registration at: https://developer.adzuna.com/

Required .env keys:
    ADZUNA_APP_ID=your_app_id
    ADZUNA_APP_KEY=your_app_key

If keys are missing, this scraper skips gracefully with a log message.
Rate limit on free tier: 1 request/second, up to 25,000/month.
"""

import time
from typing import List, Dict, Any

import requests
import structlog

from src.scrapers.base import BaseScraper
from src.utils.retry import retry_with_backoff
from src.config import settings

logger = structlog.get_logger()

BASE_URL = "https://api.adzuna.com/v1/api/jobs/us/search/{page}"
RESULTS_PER_PAGE = 50
MAX_PAGES = 4  # 200 results max to stay within free tier limits


class AdzunaScraper(BaseScraper):
    source_name = "adzuna"

    def _has_keys(self) -> bool:
        return bool(settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY)

    @retry_with_backoff(max_attempts=3)
    def _fetch_page(self, page: int) -> Dict:
        resp = requests.get(
            BASE_URL.format(page=page),
            params={
                "app_id": settings.ADZUNA_APP_ID,
                "app_key": settings.ADZUNA_APP_KEY,
                "results_per_page": RESULTS_PER_PAGE,
                "what": "software engineering intern",
                "content-type": "application/json",
                "sort_by": "date",
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def fetch(self) -> List[Dict[str, Any]]:
        if not self._has_keys():
            logger.info(
                "adzuna_skipped",
                reason="ADZUNA_APP_ID / ADZUNA_APP_KEY not set in .env",
                action="Register free at https://developer.adzuna.com/",
            )
            return []

        all_jobs: List[Dict] = []
        for page in range(1, MAX_PAGES + 1):
            try:
                data = self._fetch_page(page)
                results = data.get("results") or []
                if not results:
                    break
                all_jobs.extend(results)
                time.sleep(1)  # 1 req/sec rate limit
            except Exception as exc:
                logger.warning("adzuna_page_failed", page=page, error=str(exc))
                break

        logger.info("adzuna_fetch_complete", total=len(all_jobs))
        return all_jobs

    def parse(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        location_data = raw.get("location") or {}
        display_name = location_data.get("display_name") or "Remote/Unknown"
        area = location_data.get("area") or []
        location = display_name or (", ".join(area[-2:]) if area else "Remote/Unknown")

        company = (raw.get("company") or {}).get("display_name") or "Unknown"

        raw_date = raw.get("created") or ""
        posting_date = raw_date[:10] if raw_date else None

        return {
            "title": (raw.get("title") or "Software Intern")[:500],
            "company": company[:200],
            "location": location[:200],
            "url": raw.get("redirect_url") or "",
            "source": self.source_name,
            "posting_date": posting_date,
            "tags": ["internship", "adzuna"],
        }
