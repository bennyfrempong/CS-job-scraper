"""
HackerNews "Who is Hiring?" scraper.

Strategy:
  1. Use the HN Algolia API to find the latest monthly "Ask HN: Who is Hiring?" thread
     posted by the official `whoishiring` account.
  2. Search all comments in that thread for the keyword "intern" to surface only
     internship-relevant replies.
  3. Parse each comment's first line (typically: Company | Role | Location) as the
     structured job fields.

APIs used (no key required):
  - Algolia search:  https://hn.algolia.com/api/v1/search
  - HN item detail:  https://hacker-news.firebaseio.com/v0/item/{id}.json
"""

import time
import re
from typing import List, Dict, Any

import requests
from bs4 import BeautifulSoup
import structlog

from src.scrapers.base import BaseScraper
from src.utils.retry import retry_with_backoff

logger = structlog.get_logger()

ALGOLIA_BASE = "https://hn.algolia.com/api/v1"


class HackerNewsScraper(BaseScraper):
    source_name = "hackernews"

    # ── Internal helpers ─────────────────────────────────────────────────────────

    @retry_with_backoff(max_attempts=3)
    def _get(self, url: str, params: Dict) -> Dict:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _get_latest_hiring_story_id(self) -> int:
        """Return the objectID of the most recent 'Ask HN: Who is Hiring?' thread."""
        from datetime import datetime, timedelta
        # Only look in threads from the past 90 days
        cutoff = int((datetime.utcnow() - timedelta(days=90)).timestamp())

        data = self._get(
            f"{ALGOLIA_BASE}/search",
            params={
                "query": "Ask HN: Who is hiring",
                "tags": "ask_hn",              # only Ask HN story type
                "hitsPerPage": 10,
                "numericFilters": f"created_at_i>{cutoff}",
                "attributesToRetrieve": "objectID,title,author,created_at",
            },
        )
        # Prefer posts from the official whoishiring account
        for hit in data.get("hits", []):
            title = hit.get("title", "").lower()
            if "who is hiring" in title:
                story_id = int(hit["objectID"])
                logger.info("found_hn_hiring_thread", story_id=story_id, title=hit["title"])
                return story_id

        # Fallback: any matching result within the window
        hits = data.get("hits", [])
        if hits:
            return int(hits[0]["objectID"])
        raise ValueError("Could not locate a recent HN Who's Hiring thread")

    def _fetch_intern_comments(self, story_id: int) -> List[Dict]:
        """Paginate through all comments in the thread that mention 'intern'."""
        all_hits: List[Dict] = []
        page = 0

        while True:
            data = self._get(
                f"{ALGOLIA_BASE}/search",
                params={
                    "tags": f"comment,story_{story_id}",
                    "query": "intern",
                    "hitsPerPage": 100,
                    "page": page,
                    "attributesToRetrieve": "objectID,comment_text,author,created_at",
                },
            )
            hits = data.get("hits", [])
            all_hits.extend(hits)

            nb_pages = data.get("nbPages", 1)
            if page >= nb_pages - 1:
                break
            page += 1
            time.sleep(0.5)

        return all_hits

    # ── BaseScraper interface ────────────────────────────────────────────────────

    def fetch(self) -> List[Dict[str, Any]]:
        story_id = self._get_latest_hiring_story_id()
        return self._fetch_intern_comments(story_id)

    def parse(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        html = raw.get("comment_text") or ""
        clean = BeautifulSoup(html, "lxml").get_text(separator=" ")

        # First non-empty line is typically "Company | Role | Location | ..."
        lines = [ln.strip() for ln in clean.splitlines() if ln.strip()]
        header = lines[0] if lines else ""

        # Split on pipe, slash, or " - "
        parts = [p.strip() for p in re.split(r"\s*[|/]\s*|\s+-\s+", header) if p.strip()]
        company = parts[0] if parts else "Unknown"
        title = parts[1] if len(parts) > 1 else "Software Intern"
        location = parts[2] if len(parts) > 2 else "Remote/Unknown"

        # Posting date (ISO string → date portion)
        raw_date = raw.get("created_at") or ""
        posting_date = raw_date[:10] if raw_date else None

        return {
            "title": title[:500],
            "company": company[:200],
            "location": location[:200],
            "url": f"https://news.ycombinator.com/item?id={raw.get('objectID', '')}",
            "source": self.source_name,
            "posting_date": posting_date,
            "tags": ["internship", "hackernews"],
        }
