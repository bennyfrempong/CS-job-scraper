"""
Wellfound (AngelList) scraper.

Wellfound is a JavaScript-rendered Next.js app. We attempt two strategies:

Strategy 1 — __NEXT_DATA__ extraction:
  Next.js apps embed their initial server-side data as JSON in a
  <script id="__NEXT_DATA__"> tag. If present, this gives us structured
  job data without needing a headless browser.

Strategy 2 — JSON-LD structured data:
  Some pages embed schema.org/JobPosting markup in <script type="application/ld+json">.

If both fail (likely due to client-side rendering), we return [] and log a warning.
This is expected behaviour and does NOT crash the pipeline.

Future upgrade: swap requests for Playwright in Week 3 if this consistently returns 0.
"""

import json
import time
import random
from typing import List, Dict, Any

import requests
from bs4 import BeautifulSoup
import structlog

from src.scrapers.base import BaseScraper

logger = structlog.get_logger()

SEARCH_URL = "https://wellfound.com/jobs?role=Software+Engineer&jobType=Internship"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


class WellfoundScraper(BaseScraper):
    source_name = "wellfound"

    def fetch(self) -> List[Dict[str, Any]]:
        try:
            time.sleep(1)
            resp = requests.get(
                SEARCH_URL,
                headers={
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=15,
            )

            if resp.status_code != 200:
                logger.warning("wellfound_non_200", status=resp.status_code)
                return []

            soup = BeautifulSoup(resp.text, "lxml")

            # Strategy 1: __NEXT_DATA__ JSON blob
            jobs = self._parse_next_data(soup)
            if jobs:
                logger.info("wellfound_next_data_success", count=len(jobs))
                return jobs

            # Strategy 2: JSON-LD structured data
            jobs = self._parse_jsonld(soup)
            if jobs:
                logger.info("wellfound_jsonld_success", count=len(jobs))
                return jobs

            logger.warning(
                "wellfound_zero_results",
                note="JS-rendered content not found. "
                     "Consider upgrading to Playwright in Week 3.",
            )
            return []

        except Exception as exc:
            logger.warning(
                "wellfound_fetch_failed",
                error=str(exc),
                note="Silently failing — pipeline continues",
            )
            return []

    def _parse_next_data(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract jobs from Next.js server-side data blob."""
        script = soup.find("script", id="__NEXT_DATA__")
        if not script or not script.string:
            return []

        try:
            data = json.loads(script.string)
            # Walk the nested props to find job listings
            props = data.get("props", {}).get("pageProps", {})
            jobs_raw = (
                props.get("jobs")
                or props.get("jobListings")
                or props.get("startups", [{}])[0].get("jobs", [])
                if props.get("startups") else []
            )
            return [self._normalize(j) for j in (jobs_raw or []) if j]
        except (json.JSONDecodeError, Exception):
            return []

    def _parse_jsonld(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract jobs from schema.org/JobPosting JSON-LD."""
        results = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") == "JobPosting":
                        results.append(self._from_jsonld(item))
            except Exception:
                continue
        return results

    def _normalize(self, raw: Dict) -> Dict:
        return {
            "title": raw.get("title") or raw.get("name") or "Software Intern",
            "company": (raw.get("company") or {}).get("name") or raw.get("companyName") or "Unknown",
            "location": raw.get("location") or raw.get("locationDisplayName") or "Remote/Unknown",
            "url": raw.get("url") or raw.get("applyUrl") or SEARCH_URL,
        }

    def _from_jsonld(self, data: Dict) -> Dict:
        loc = data.get("jobLocation") or {}
        address = loc.get("address") or {}
        return {
            "title": data.get("title", "Software Intern"),
            "company": (data.get("hiringOrganization") or {}).get("name", "Unknown"),
            "location": address.get("addressLocality") or "Remote/Unknown",
            "url": data.get("url", SEARCH_URL),
        }

    def parse(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": raw.get("title", "Software Intern")[:500],
            "company": raw.get("company", "Unknown")[:200],
            "location": raw.get("location", "Remote/Unknown")[:200],
            "url": raw.get("url", ""),
            "source": self.source_name,
            "posting_date": None,
            "tags": ["internship", "wellfound", "startup"],
        }
