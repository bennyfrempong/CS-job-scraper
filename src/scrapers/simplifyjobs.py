"""
SimplifyJobs GitHub scraper — fixed for actual repo structure.

Repo structure (as of Summer 2026):
  - master branch: HTML landing page / category index
  - dev branch: The actual markdown job table (all listings)

Strategy (in priority order):
  1. Fetch listings.json from dev branch (JSON is most stable)
  2. Fall back to parsing the dev branch README markdown table
  3. Use GITHUB_TOKEN header to avoid rate limiting on both

Rate limits without token: 60 raw requests/hour per IP
Rate limits with token: 5,000/hour — set GITHUB_TOKEN in .env
"""

import re
import base64
import time
from typing import List, Dict, Any

import requests
import structlog

from src.scrapers.base import BaseScraper
from src.utils.retry import retry_with_backoff
from src.config import settings

logger = structlog.get_logger()

REPO = "SimplifyJobs/Summer2026-Internships"
BRANCH = "dev"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
API_BASE = f"https://api.github.com/repos/{REPO}/contents"

# Some repos store structured JSON alongside the README
JSON_PATHS = ["listings.json", ".github/scripts/listings.json", "data/listings.json"]


class SimplifyJobsScraper(BaseScraper):
    source_name = "simplifyjobs"

    def _headers(self) -> Dict[str, str]:
        headers = {"User-Agent": "JobPipeline/1.0"}
        if settings.GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
        return headers

    @retry_with_backoff(max_attempts=3)
    def _get(self, url: str) -> requests.Response:
        time.sleep(1)  # be polite — avoid rate limits
        resp = requests.get(url, headers=self._headers(), timeout=15)
        return resp

    # ── Strategy 1: JSON file ────────────────────────────────────────────────

    def _try_json(self) -> List[Dict]:
        """Try to load structured JSON listing file from the repo."""
        for path in JSON_PATHS:
            resp = self._get(f"{RAW_BASE}/{path}")
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    jobs = data if isinstance(data, list) else data.get("listings", [])
                    logger.info("simplifyjobs_json_success", path=path, count=len(jobs))
                    return [self._from_json_item(j) for j in jobs if j]
                except Exception:
                    continue
        return []

    def _from_json_item(self, item: Dict) -> Dict:
        return {
            "company": item.get("company_name") or item.get("company") or "Unknown",
            "title": item.get("title") or item.get("role") or "Software Intern",
            "location": ", ".join(item.get("locations") or []) or item.get("location") or "Remote/Unknown",
            "url": item.get("url") or item.get("apply_url") or "",
        }

    # ── Strategy 2: Markdown table parser ───────────────────────────────────

    def _try_readme(self) -> List[Dict]:
        """Parse the dev branch README markdown table."""
        resp = self._get(f"{RAW_BASE}/README.md")
        if resp.status_code == 429:
            logger.warning(
                "simplifyjobs_rate_limited",
                note="Set GITHUB_TOKEN in .env for higher rate limits",
            )
            return []
        if resp.status_code != 200:
            logger.warning("simplifyjobs_readme_failed", status=resp.status_code)
            return []

        return self._parse_table(resp.text)

    @staticmethod
    def _extract_url(cell: str) -> str:
        match = re.search(r'\[.*?\]\((https?://[^\)]+)\)', cell)
        return match.group(1) if match else ""

    @staticmethod
    def _clean_cell(cell: str) -> str:
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', cell)
        text = re.sub(r'\[.*?\]\(.*?\)', '', text)
        text = re.sub(r'[^\x00-\x7F]', '', text)  # strip non-ASCII (emoji)
        return text.strip()

    def _parse_table(self, content: str) -> List[Dict]:
        rows = []
        last_company = ""
        in_table = False

        for line in content.splitlines():
            line = line.strip()
            if not line.startswith("|"):
                if in_table:
                    in_table = False
                continue

            # Detect header row (contains "Company" and some role/position column)
            if any(kw in line for kw in ("Company", "Role", "Position", "Title")):
                in_table = True
                continue
            if "---" in line:
                continue
            if not in_table:
                continue

            cells = [c.strip() for c in line.split("|")]
            cells = [c for c in cells if c != ""]
            if len(cells) < 3:
                continue

            company_cell = cells[0]
            role_cell = cells[1] if len(cells) > 1 else ""
            location_cell = cells[2] if len(cells) > 2 else ""
            link_cell = cells[3] if len(cells) > 3 else ""

            # Handle ↳ continuation rows
            if self._clean_cell(company_cell) in ("", "?", "↳") or "↳" in company_cell:
                company = last_company
            else:
                company = self._clean_cell(company_cell)
                if company:
                    last_company = company

            role = self._clean_cell(role_cell)
            if not role or role == "---":
                continue

            # Only keep intern-relevant roles
            if not any(kw in role.lower() for kw in ("intern", "co-op", "coop", "student")):
                continue

            rows.append({
                "company": company or "Unknown",
                "title": role,
                "location": self._clean_cell(location_cell) or "Remote/Unknown",
                "url": self._extract_url(link_cell),
            })

        logger.info("simplifyjobs_table_parsed", count=len(rows))
        return rows

    # ── Main fetch ───────────────────────────────────────────────────────────

    def fetch(self) -> List[Dict[str, Any]]:
        # Try JSON first (most stable)
        jobs = self._try_json()
        if jobs:
            return jobs

        # Fall back to README table
        return self._try_readme()

    def parse(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": raw.get("title", "Software Intern")[:500],
            "company": raw.get("company", "Unknown")[:200],
            "location": raw.get("location", "Remote/Unknown")[:200],
            "url": raw.get("url", ""),
            "source": self.source_name,
            "posting_date": None,
            "tags": ["internship", "simplifyjobs"],
        }
