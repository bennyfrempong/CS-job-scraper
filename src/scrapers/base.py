from abc import ABC, abstractmethod
from typing import List, Dict, Any
import structlog

logger = structlog.get_logger()


class BaseScraper(ABC):
    """
    Abstract base class for all job scrapers.

    Subclasses must implement:
        - source_name (class attribute)
        - fetch()  → list of raw dicts from the data source
        - parse()  → converts one raw dict into our normalized job schema

    The run() method orchestrates fetch + parse and is the public entry point.
    Individual parse failures are caught and logged without aborting the run.
    """

    source_name: str = ""

    # ── Abstract interface ───────────────────────────────────────────────────────

    @abstractmethod
    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch raw data from the source. Must return a list of raw job dicts."""

    @abstractmethod
    def parse(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse one raw job dict into our normalized schema.

        Expected output keys:
            title, company, location, url, source, posting_date, tags
        """

    # ── Public entry point ───────────────────────────────────────────────────────

    def run(self) -> List[Dict[str, Any]]:
        """
        Execute the full scrape cycle: fetch all raw items, parse each one.

        - A failure in fetch() is re-raised (handled by the Celery task).
        - A failure in parse() logs a warning and skips that item.
        """
        log = logger.bind(source=self.source_name)

        raw_jobs = self.fetch()
        log.info("fetched_raw_jobs", count=len(raw_jobs))

        parsed: List[Dict[str, Any]] = []
        for raw in raw_jobs:
            try:
                job = self.parse(raw)
                if job:
                    parsed.append(job)
            except Exception as exc:
                log.warning(
                    "parse_failed",
                    error=str(exc),
                    error_type=type(exc).__name__,
                    raw_preview=str(raw)[:200],
                )

        log.info("parsed_jobs", count=len(parsed))
        return parsed
