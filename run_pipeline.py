#!/usr/bin/env python3
"""
Manual pipeline runner — use this to verify the full stack works end-to-end
before Celery is wired in.

Usage:
    python run_pipeline.py                 # run all 3 Week-1 scrapers
    python run_pipeline.py hackernews      # run one scraper by name
    python run_pipeline.py remoteok greenhouse
"""

import sys
from datetime import datetime, timezone

from src.utils.logger import setup_logging
from src.config import settings
from src.database.session import db_session
from src.database.models import ScrapeRun, ScrapeError
from src.scrapers.hackernews import HackerNewsScraper
from src.scrapers.remoteok import RemoteOKScraper
from src.scrapers.greenhouse import GreenhouseScraper
from src.scrapers.lever import LeverScraper
from src.scrapers.simplifyjobs import SimplifyJobsScraper
from src.scrapers.indeed import IndeedScraper
from src.scrapers.wellfound import WellfoundScraper
from src.scrapers.adzuna import AdzunaScraper
from src.scrapers.themuse import TheMuseScraper
from src.scrapers.usajobs import USAJobsScraper
from src.pipeline.cleaner import clean_job
from src.pipeline.normalizer import normalize_jobs
from src.pipeline.deduplicator import upsert_jobs

import structlog

logger = structlog.get_logger()

ALL_SCRAPERS = {
    "hackernews":   HackerNewsScraper,
    "remoteok":     RemoteOKScraper,
    "greenhouse":   GreenhouseScraper,
    "lever":        LeverScraper,
    "simplifyjobs": SimplifyJobsScraper,
    "indeed":       IndeedScraper,
    "wellfound":    WellfoundScraper,
    "adzuna":       AdzunaScraper,
    "themuse":      TheMuseScraper,
    "usajobs":      USAJobsScraper,
}


def run_scraper(name: str, scraper_cls) -> None:
    log = logger.bind(source=name)
    log.info("scraper_starting")

    with db_session() as db:
        # Open a scrape_run record
        run = ScrapeRun(source=name, started_at=datetime.now(timezone.utc))
        db.add(run)
        db.flush()

        try:
            scraper = scraper_cls()
            raw_jobs = scraper.run()

            cleaned = [clean_job(j) for j in raw_jobs]
            normalized = normalize_jobs(cleaned)
            new_count, skipped = upsert_jobs(normalized, db)

            run.completed_at = datetime.now(timezone.utc)
            run.new_listings = new_count
            run.skipped_dupes = skipped
            run.error_count = 0
            run.status = "success"

            log.info(
                "scraper_complete",
                new=new_count,
                skipped_dupes=skipped,
                total_raw=len(raw_jobs),
            )

        except Exception as exc:
            # Roll back the session so we can write the error record cleanly.
            # The upsert may have left the session in a failed-transaction state.
            try:
                db.rollback()
            except Exception:
                pass

            error = ScrapeError(
                source=name,
                error_type=type(exc).__name__,
                error_message=str(exc),
                occurred_at=datetime.now(timezone.utc),
            )
            db.add(error)

            run.completed_at = datetime.now(timezone.utc)
            run.error_count = 1
            run.status = "failed"

            log.error("scraper_failed", error=str(exc), error_type=type(exc).__name__)


def main() -> None:
    setup_logging(settings.LOG_LEVEL)

    targets = sys.argv[1:] if len(sys.argv) > 1 else list(ALL_SCRAPERS.keys())

    print(f"\n{'='*60}")
    print(f"  Job Pipeline Manual Run — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Scrapers: {', '.join(targets)}")
    print(f"{'='*60}\n")

    for name in targets:
        if name not in ALL_SCRAPERS:
            print(f"[!] Unknown scraper: {name!r}. Valid: {list(ALL_SCRAPERS)}")
            continue
        run_scraper(name, ALL_SCRAPERS[name])

    print(f"\n{'='*60}")
    print("  Run complete. Check your job_postings table.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
