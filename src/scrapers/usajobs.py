"""
USAJobs scraper.

The US federal government's official job board exposes a public REST API.
Free registration at: https://developer.usajobs.gov/

Required .env keys:
    USAJOBS_API_KEY=your_api_key
    USAJOBS_EMAIL=your@email.com   (used as User-Agent per their requirement)

If keys are missing, this scraper skips gracefully.
"""

from typing import List, Dict, Any

import requests
import structlog

from src.scrapers.base import BaseScraper
from src.utils.retry import retry_with_backoff
from src.config import settings

logger = structlog.get_logger()

BASE_URL = "https://data.usajobs.gov/api/search"
RESULTS_PER_PAGE = 50


class USAJobsScraper(BaseScraper):
    source_name = "usajobs"

    def _has_keys(self) -> bool:
        return bool(settings.USAJOBS_API_KEY and settings.USAJOBS_EMAIL)

    def _headers(self) -> Dict[str, str]:
        return {
            "Host": "data.usajobs.gov",
            "User-Agent": settings.USAJOBS_EMAIL,
            "Authorization-Key": settings.USAJOBS_API_KEY,
        }

    @retry_with_backoff(max_attempts=3)
    def _fetch_page(self, page: int) -> Dict:
        resp = requests.get(
            BASE_URL,
            headers=self._headers(),
            params={
                "Keyword": "computer science intern software engineer intern",
                "ResultsPerPage": RESULTS_PER_PAGE,
                "Page": page,
                "SortField": "OpenDate",
                "SortDirection": "Descending",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def fetch(self) -> List[Dict[str, Any]]:
        if not self._has_keys():
            logger.info(
                "usajobs_skipped",
                reason="USAJOBS_API_KEY / USAJOBS_EMAIL not set in .env",
                action="Register free at https://developer.usajobs.gov/",
            )
            return []

        all_jobs: List[Dict] = []
        page = 1

        while True:
            try:
                data = self._fetch_page(page)
                search_result = data.get("SearchResult") or {}
                items = search_result.get("SearchResultItems") or []

                if not items:
                    break

                all_jobs.extend(items)

                total = search_result.get("SearchResultCountAll", 0)
                if len(all_jobs) >= min(total, 200):  # cap at 200
                    break

                page += 1

            except Exception as exc:
                logger.warning("usajobs_page_failed", page=page, error=str(exc))
                break

        logger.info("usajobs_fetch_complete", total=len(all_jobs))
        return all_jobs

    def parse(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        matched = raw.get("MatchedObjectDescriptor") or {}

        # Location
        locations = matched.get("PositionLocation") or []
        location = locations[0].get("LocationName") if locations else "Remote/Unknown"

        # Salary / Pay grade (useful for filtering)
        pay = matched.get("PositionRemuneration") or [{}]
        grade = (pay[0].get("Description") or "")[:50] if pay else ""

        # Date
        raw_date = matched.get("PublicationStartDate") or ""
        posting_date = raw_date[:10] if raw_date else None

        tags = ["internship", "usajobs", "federal", "government"]
        if grade:
            tags.append(grade.lower())

        return {
            "title": (matched.get("PositionTitle") or "Federal Intern")[:500],
            "company": (matched.get("DepartmentName") or "US Government")[:200],
            "location": (location or "Remote/Unknown")[:200],
            "url": matched.get("ApplyURI", [""])[0] if matched.get("ApplyURI") else "",
            "source": self.source_name,
            "posting_date": posting_date,
            "tags": tags[:20],
        }
