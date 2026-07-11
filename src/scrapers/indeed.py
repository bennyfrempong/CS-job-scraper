"""
Indeed HTML scraper.

Indeed has no public API (deprecated 2021). We parse their public job search HTML.
This is the most fragile scraper in the pipeline — Indeed actively defends against
automated access with rate limiting, JS challenges, and dynamic class names.

Design principles:
  - Multiple CSS selector fallbacks so one broken selector doesn't kill the run
  - All failures are caught and logged — this scraper NEVER crashes the pipeline
  - Rotated User-Agent strings and a request delay to reduce bot detection
  - If we get 0 results, it's logged as a warning — the canary will flag it

Interview talking point: "Indeed is our canary scraper. We treat 0-result runs
as a signal that the site structure changed, not as an error."
"""

import time
import random
from typing import List, Dict, Any

import requests
from bs4 import BeautifulSoup
import structlog

from src.scrapers.base import BaseScraper

logger = structlog.get_logger()

SEARCH_URL = (
    "https://www.indeed.com/jobs"
    "?q=software+engineering+intern"
    "&sort=date"
    "&fromage=14"  # last 14 days only
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]


class IndeedScraper(BaseScraper):
    source_name = "indeed"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    def fetch(self) -> List[Dict[str, Any]]:
        """
        Attempt to fetch Indeed job cards.
        Returns empty list on any failure — this scraper never raises.
        """
        try:
            time.sleep(2)  # polite delay before hitting Indeed
            resp = requests.get(
                SEARCH_URL,
                headers=self._get_headers(),
                timeout=15,
                allow_redirects=True,
            )

            if resp.status_code != 200:
                logger.warning(
                    "indeed_non_200",
                    status=resp.status_code,
                    note="May be rate-limited or blocked",
                )
                return []

            soup = BeautifulSoup(resp.text, "lxml")

            # Indeed uses dynamically generated class names — try multiple strategies
            jobs = (
                self._parse_strategy_mosaic(soup)
                or self._parse_strategy_jobcard(soup)
                or self._parse_strategy_jsonld(soup)
            )

            if not jobs:
                logger.warning(
                    "indeed_zero_results",
                    note="Page structure may have changed or request was blocked",
                    url=SEARCH_URL,
                )

            return jobs

        except Exception as exc:
            logger.warning(
                "indeed_fetch_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                note="Silently failing — pipeline continues",
            )
            return []

    def _parse_strategy_mosaic(self, soup: BeautifulSoup) -> List[Dict]:
        """Indeed's current 'mosaic' card layout."""
        cards = soup.select("div.job_seen_beacon") or soup.select("div[data-jk]")
        return [self._extract_card(card) for card in cards if card]

    def _parse_strategy_jobcard(self, soup: BeautifulSoup) -> List[Dict]:
        """Older jobcard layout fallback."""
        cards = soup.select("div.jobsearch-SerpJobCard") or soup.select("li.result")
        return [self._extract_card(card) for card in cards if card]

    def _parse_strategy_jsonld(self, soup: BeautifulSoup) -> List[Dict]:
        """Look for JSON-LD structured data embedded in the page."""
        import json
        results = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "JobPosting":
                            results.append(self._from_jsonld(item))
                elif data.get("@type") == "JobPosting":
                    results.append(self._from_jsonld(data))
            except Exception:
                continue
        return results

    def _extract_card(self, card) -> Dict[str, Any]:
        title_el = (
            card.select_one("h2.jobTitle span")
            or card.select_one("a.jobtitle")
            or card.select_one("[data-testid='job-title']")
        )
        company_el = (
            card.select_one("span.companyName")
            or card.select_one("[data-testid='company-name']")
        )
        location_el = (
            card.select_one("div.companyLocation")
            or card.select_one("[data-testid='job-location']")
        )
        link_el = card.select_one("a[id^='job_']") or card.select_one("a.jobtitle")
        href = link_el.get("href", "") if link_el else ""
        url = f"https://www.indeed.com{href}" if href.startswith("/") else href

        return {
            "title": title_el.get_text(strip=True) if title_el else "Software Intern",
            "company": company_el.get_text(strip=True) if company_el else "Unknown",
            "location": location_el.get_text(strip=True) if location_el else "Remote/Unknown",
            "url": url,
        }

    def _from_jsonld(self, data: Dict) -> Dict[str, Any]:
        loc = data.get("jobLocation") or {}
        address = loc.get("address") or {}
        location = (
            address.get("addressLocality")
            or address.get("addressRegion")
            or "Remote/Unknown"
        )
        return {
            "title": data.get("title", "Software Intern"),
            "company": (data.get("hiringOrganization") or {}).get("name", "Unknown"),
            "location": location,
            "url": data.get("url") or data.get("identifier", {}).get("value", ""),
        }

    def parse(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": raw.get("title", "Software Intern")[:500],
            "company": raw.get("company", "Unknown")[:200],
            "location": raw.get("location", "Remote/Unknown")[:200],
            "url": raw.get("url", ""),
            "source": self.source_name,
            "posting_date": None,
            "tags": ["internship", "indeed"],
        }
