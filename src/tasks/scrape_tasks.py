"""
Celery scrape tasks — one @app.task per source + a coordinator task.

Each task:
  1. Opens a DB session and creates a ScrapeRun record
  2. Runs the scraper → clean → normalize → upsert pipeline
  3. Updates the ScrapeRun with final counts and status
  4. Logs any exception to ScrapeError without crashing

The coordinator task (scrape.all) dispatches all individual tasks
as independent Celery jobs so they run in parallel on the worker pool.

Canary alert: if a scraper returns 0 results it logs a WARNING — useful for
detecting when a source changes its structure.
"""

from datetime import datetime, timezone
from typing import Type

import structlog

from src.tasks.celery_app import app
from src.database.session import db_session
from src.database.models import ScrapeRun, ScrapeError, JobPosting
from src.scrapers.base import BaseScraper
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

logger = structlog.get_logger()


def _run_scraper_task(source_name: str, scraper_cls: Type[BaseScraper]) -> None:
    """
    Shared execution logic for all scraper tasks.
    Always writes a ScrapeRun record — success or failure.
    """
    log = logger.bind(source=source_name)

    with db_session() as db:
        run = ScrapeRun(
            source=source_name,
            started_at=datetime.now(timezone.utc),
            status="running",
        )
        db.add(run)
        db.flush()

        try:
            scraper = scraper_cls()
            raw_jobs = scraper.run()

            # Canary: warn on zero results (site may have changed)
            if len(raw_jobs) == 0:
                log.warning("zero_results_canary", source=source_name)

            cleaned = [clean_job(j) for j in raw_jobs]
            normalized = normalize_jobs(cleaned)
            new_count, skipped = upsert_jobs(normalized, db)

            # --- Cast out dead listings ---
            db.query(JobPosting).filter(
                JobPosting.source == source_name,
                JobPosting.is_active == True,
                JobPosting.scraped_at < run.started_at
            ).update({"is_active": False})

            run.completed_at = datetime.now(timezone.utc)
            run.new_listings = new_count
            run.skipped_dupes = skipped
            run.error_count = 0
            run.status = "success"

            log.info(
                "task_complete",
                new=new_count,
                skipped_dupes=skipped,
                total_raw=len(raw_jobs),
            )

        except Exception as exc:
            try:
                db.rollback()
            except Exception:
                pass

            db.add(ScrapeError(
                source=source_name,
                error_type=type(exc).__name__,
                error_message=str(exc)[:2000],
                occurred_at=datetime.now(timezone.utc),
            ))
            run.completed_at = datetime.now(timezone.utc)
            run.error_count = 1
            run.status = "failed"

            log.error("task_failed", error=str(exc)[:500], error_type=type(exc).__name__)


# ── Individual scraper tasks ─────────────────────────────────────────────────

@app.task(name="scrape.hackernews")
def scrape_hackernews():
    _run_scraper_task("hackernews", HackerNewsScraper)

@app.task(name="scrape.remoteok")
def scrape_remoteok():
    _run_scraper_task("remoteok", RemoteOKScraper)

@app.task(name="scrape.greenhouse")
def scrape_greenhouse():
    _run_scraper_task("greenhouse", GreenhouseScraper)

@app.task(name="scrape.lever")
def scrape_lever():
    _run_scraper_task("lever", LeverScraper)

@app.task(name="scrape.simplifyjobs")
def scrape_simplifyjobs():
    _run_scraper_task("simplifyjobs", SimplifyJobsScraper)

@app.task(name="scrape.indeed")
def scrape_indeed():
    _run_scraper_task("indeed", IndeedScraper)

@app.task(name="scrape.wellfound")
def scrape_wellfound():
    _run_scraper_task("wellfound", WellfoundScraper)

@app.task(name="scrape.adzuna")
def scrape_adzuna():
    _run_scraper_task("adzuna", AdzunaScraper)

@app.task(name="scrape.themuse")
def scrape_themuse():
    _run_scraper_task("themuse", TheMuseScraper)

@app.task(name="scrape.usajobs")
def scrape_usajobs():
    _run_scraper_task("usajobs", USAJobsScraper)


# ── Coordinator task ─────────────────────────────────────────────────────────

ALL_TASKS = [
    scrape_hackernews,
    scrape_remoteok,
    scrape_greenhouse,
    scrape_lever,
    scrape_simplifyjobs,
    scrape_indeed,
    scrape_wellfound,
    scrape_adzuna,
    scrape_themuse,
    scrape_usajobs,
]

@app.task(name="scrape.all")
def run_all_scrapers():
    """
    Dispatch all individual scraper tasks as independent Celery jobs.
    They run concurrently — one per worker slot.
    Beat schedule triggers this task every 6 hours.
    """
    logger.info("dispatching_all_scrapers", count=len(ALL_TASKS))
    for task in ALL_TASKS:
        task.delay()
