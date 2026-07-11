"""
RemoteOK scraper.

RemoteOK exposes a public JSON feed at https://remoteok.com/api with no auth required.
The first element is metadata — we skip it and filter the rest for CS/internship relevance.

We include a job if:
  - Its title or tags contain an internship keyword ("intern", "co-op", etc.), OR
  - Its tags overlap with common CS keywords (python, javascript, backend, etc.)

This gives broad tech coverage while keeping noise low.
"""

import time
from typing import List, Dict, Any

import requests
import structlog

from src.scrapers.base import BaseScraper
from src.utils.retry import retry_with_backoff

logger = structlog.get_logger()

API_URL = "https://remoteok.com/api"

INTERN_KEYWORDS = {"intern", "internship", "co-op", "coop", "student", "trainee"}
CS_TAGS = {
    "python", "javascript", "typescript", "backend", "frontend",
    "fullstack", "full-stack", "software", "engineering", "data",
    "machine-learning", "ml", "ai", "devops", "cloud", "golang", "rust",
    "java", "kotlin", "swift", "ios", "android", "react", "node",
}


class RemoteOKScraper(BaseScraper):
    source_name = "remoteok"

    @retry_with_backoff(max_attempts=3)
    def fetch(self) -> List[Dict[str, Any]]:
        resp = requests.get(
            API_URL,
            headers={
                # RemoteOK requires a non-empty User-Agent or returns 403
                "User-Agent": "JobPipeline/1.0 (educational aggregator project)"
            },
            timeout=15,
        )
        resp.raise_for_status()

        data = resp.json()
        # First element is the legal/metadata object — always skip it
        jobs = data[1:] if isinstance(data, list) and len(data) > 1 else []

        filtered: List[Dict] = []
        for job in jobs:
            tags = [str(t).lower() for t in (job.get("tags") or [])]
            title = (job.get("position") or "").lower()
            desc = (job.get("description") or "")[:500].lower()

            is_intern = any(kw in title or kw in " ".join(tags) or kw in desc for kw in INTERN_KEYWORDS)
            has_cs_tag = bool(CS_TAGS & set(tags))

            if is_intern or has_cs_tag:
                filtered.append(job)

        logger.info("remoteok_filtered", total=len(jobs), kept=len(filtered))
        return filtered

    def parse(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        tags = [str(t).lower() for t in (raw.get("tags") or [])]

        # Location: RemoteOK often has an explicit field; fallback to "Remote"
        location = raw.get("location") or "Remote"

        # Posting date: epoch timestamp or ISO string
        date_val = raw.get("date") or ""
        posting_date = str(date_val)[:10] if date_val else None

        return {
            "title": (raw.get("position") or "Software Role")[:500],
            "company": (raw.get("company") or "Unknown")[:200],
            "location": location[:200],
            "url": raw.get("url") or raw.get("apply_url") or "",
            "source": self.source_name,
            "posting_date": posting_date,
            "tags": tags[:20],
        }
