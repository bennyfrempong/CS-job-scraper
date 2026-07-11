"""
Lever Job Board scraper.

Lever exposes a fully public, unauthenticated REST API for every company using
their platform:

    GET https://api.lever.co/v0/postings/{company}?mode=json

Returns a JSON array of posting objects. We iterate over 20 curated tech companies,
filter for intern/co-op titles, and map to our schema.

Error handling: 404 → company not on Lever (skip silently). Any other error → log and continue.
"""

import time
from typing import List, Dict, Any, Optional

import requests
import structlog

from src.scrapers.base import BaseScraper
from src.utils.retry import retry_with_backoff

logger = structlog.get_logger()

POSTINGS_API = "https://api.lever.co/v0/postings/{company}?mode=json"

INTERN_KEYWORDS = {"intern", "internship", "co-op", "coop", "student", "apprentice"}

COMPANIES: List[str] = [
    "netflix",
    "coinbase",
    "reddit",
    "duolingo",
    "airtable",
    "plaid",
    "verkada",
    "asana",
    "intercom",
    "gusto",
    "postman",
    "loom",
    "mercury",
    "canva",
    "lattice",
    "dbtlabs",
    "wandb",
    "figma",
    "notion",
    "linear",
]


class LeverScraper(BaseScraper):
    source_name = "lever"

    @retry_with_backoff(max_attempts=3)
    def _fetch_company(self, company: str) -> Optional[List[Dict]]:
        """Fetch all postings for a single company. Returns None on 404."""
        try:
            resp = requests.get(
                POSTINGS_API.format(company=company),
                timeout=10,
            )
            if resp.status_code == 404:
                logger.debug("lever_company_not_found", company=company)
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as exc:
            logger.warning("lever_http_error", company=company, error=str(exc))
            return None

    def fetch(self) -> List[Dict[str, Any]]:
        all_jobs: List[Dict] = []

        for company in COMPANIES:
            postings = self._fetch_company(company)
            if not postings:
                continue

            intern_postings = [
                p for p in postings
                if any(kw in (p.get("text") or "").lower() for kw in INTERN_KEYWORDS)
            ]

            for p in intern_postings:
                p["_company_slug"] = company

            all_jobs.extend(intern_postings)
            logger.debug(
                "lever_company_scraped",
                company=company,
                total=len(postings),
                interns=len(intern_postings),
            )
            time.sleep(0.5)

        logger.info("lever_fetch_complete", total_intern_jobs=len(all_jobs))
        return all_jobs

    def parse(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        # Location lives inside categories
        categories = raw.get("categories") or {}
        location = (
            categories.get("location")
            or categories.get("commitment")
            or "Remote/Unknown"
        )

        # Company name — Lever includes it in the posting or we fall back to slug
        company = (
            raw.get("company")
            or raw.get("_company_slug", "")
        ).replace("-", " ").title()

        # Posting date — Lever uses millisecond epoch timestamps
        created_ms = raw.get("createdAt")
        posting_date = None
        if created_ms:
            from datetime import datetime, timezone
            posting_date = datetime.fromtimestamp(
                created_ms / 1000, tz=timezone.utc
            ).strftime("%Y-%m-%d")

        tags = ["internship", "lever"] + [
            t.lower() for t in (raw.get("tags") or []) if t
        ]

        return {
            "title": (raw.get("text") or "Software Intern")[:500],
            "company": company[:200],
            "location": str(location)[:200],
            "url": raw.get("hostedUrl") or raw.get("applyUrl") or "",
            "source": self.source_name,
            "posting_date": posting_date,
            "tags": tags[:20],
        }
