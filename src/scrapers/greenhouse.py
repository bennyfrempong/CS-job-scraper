"""
Greenhouse Job Board scraper.

Greenhouse exposes a fully public, unauthenticated REST API for every company that uses
their platform:

    GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true

We iterate over a curated list of ~20 high-signal tech companies, pull all their jobs,
and filter down to intern/co-op titles.

Error handling:
  - 404 → company uses a different board token or isn't on Greenhouse; skip silently.
  - Any other HTTP error → log and continue to next company.
  - We never crash the full scrape over one bad company endpoint.
"""

import time
from typing import List, Dict, Any, Optional

import requests
import structlog

from src.scrapers.base import BaseScraper
from src.utils.retry import retry_with_backoff

logger = structlog.get_logger()

BOARDS_API = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"

INTERN_KEYWORDS = {"intern", "internship", "co-op", "coop", "student"}

# Known Greenhouse board tokens for companies with active internship programs.
# Token is the slug used in boards.greenhouse.io/<token>
COMPANIES: List[str] = [
    "stripe",
    "ramp",
    "figma",
    "airbnb",
    "notion",
    "robinhood",
    "databricks",
    "brex",
    "benchling",
    "snyk",
    "hashicorp",
    "sourcegraph",
    "cockroachlabs",
    "retool",
    "verkada",
    "rippling",
    "airtable",
    "gusto",
    "cloudflare",
    "plaid",
]


class GreenhouseScraper(BaseScraper):
    source_name = "greenhouse"

    @retry_with_backoff(max_attempts=3)
    def _fetch_company(self, company: str) -> Optional[List[Dict]]:
        """Fetch all internship jobs for a single company. Returns None on 404."""
        try:
            resp = requests.get(
                BOARDS_API.format(company=company),
                params={"content": "true"},
                timeout=10,
            )
            if resp.status_code == 404:
                logger.debug("greenhouse_company_not_found", company=company)
                return None
            resp.raise_for_status()
            return resp.json().get("jobs", [])
        except requests.exceptions.HTTPError as exc:
            logger.warning("greenhouse_http_error", company=company, error=str(exc))
            return None

    def fetch(self) -> List[Dict[str, Any]]:
        all_jobs: List[Dict] = []

        for company in COMPANIES:
            jobs = self._fetch_company(company)
            if not jobs:
                continue

            # Filter for internship titles
            intern_jobs = [
                j for j in jobs
                if any(kw in (j.get("title") or "").lower() for kw in INTERN_KEYWORDS)
            ]

            # Attach the board token so parse() can use it for the company name
            for j in intern_jobs:
                j["_board_token"] = company

            all_jobs.extend(intern_jobs)
            logger.debug(
                "greenhouse_company_scraped",
                company=company,
                total_jobs=len(jobs),
                intern_jobs=len(intern_jobs),
            )
            time.sleep(0.5)  # be polite — one request per 500ms per company

        logger.info("greenhouse_fetch_complete", total_intern_jobs=len(all_jobs))
        return all_jobs

    def parse(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        # ── Location ─────────────────────────────────────────────────────────────
        # Greenhouse returns offices as a list or a single dict depending on version
        offices = raw.get("offices") or raw.get("location") or []
        if isinstance(offices, list) and offices:
            location = offices[0].get("name") or "Remote/Unknown"
        elif isinstance(offices, dict):
            location = offices.get("name") or "Remote/Unknown"
        else:
            location = "Remote/Unknown"

        # ── Company name ──────────────────────────────────────────────────────────
        # Prefer the board's company name if present; fall back to the token
        company_name = (
            raw.get("company_name")
            or raw.get("_board_token", "")
        ).replace("-", " ").title()

        # ── Tags from departments ─────────────────────────────────────────────────
        departments = raw.get("departments") or []
        dept_tags = [d.get("name", "").lower() for d in departments if d.get("name")]
        tags = ["internship", "greenhouse"] + dept_tags

        # ── Posting date ──────────────────────────────────────────────────────────
        raw_date = raw.get("updated_at") or ""
        posting_date = raw_date[:10] if raw_date else None

        return {
            "title": (raw.get("title") or "Software Intern")[:500],
            "company": company_name[:200],
            "location": location[:200],
            "url": raw.get("absolute_url") or "",
            "source": self.source_name,
            "posting_date": posting_date,
            "tags": [t for t in tags if t][:20],
        }
