"""
Deduplication + DB upsert.

Deduplication strategy
───────────────────────
Each job is fingerprinted before it touches the database:

    content_hash = SHA-256( title.lower() + "|" + company.lower() + "|" + location.lower() )

The `job_postings.content_hash` column has a UNIQUE constraint, so the DB
is the ultimate guard — but the Python-side check avoids unnecessary round-trips.

On re-encounter of an existing posting we update `scraped_at` to the current
timestamp (last-seen semantics) rather than creating a duplicate.

Returns
───────
(new_count, skipped_count) — used by Celery tasks to populate scrape_runs.
"""

import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple

from sqlalchemy.orm import Session
import structlog

from src.database.models import JobPosting

logger = structlog.get_logger()


def compute_hash(title: str, company: str, location: str) -> str:
    """SHA-256 fingerprint of the three key identity fields."""
    key = f"{title.strip().lower()}|{company.strip().lower()}|{location.strip().lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def upsert_jobs(
    jobs: List[Dict[str, Any]],
    db: Session,
) -> Tuple[int, int]:
    """
    Insert new jobs and refresh scraped_at on duplicates.

    Args:
        jobs: List of normalized job dicts (output of normalize_jobs).
        db:   An active SQLAlchemy Session.

    Returns:
        (new_count, skipped_count)
    """
    new_count = 0
    skipped_count = 0
    now = datetime.now(timezone.utc)

    # Guard against duplicates WITHIN this batch (same hash appearing twice
    # in one scrape run, e.g. two HN comments that parse to identical fields)
    seen_in_batch: set = set()

    for job in jobs:
        content_hash = compute_hash(
            job.get("title", ""),
            job.get("company", ""),
            job.get("location", ""),
        )

        # Skip if we already handled this hash earlier in the same batch
        if content_hash in seen_in_batch:
            skipped_count += 1
            continue
        seen_in_batch.add(content_hash)

        existing = db.query(JobPosting).filter_by(content_hash=content_hash).first()

        if existing:
            existing.scraped_at = now  # refresh last-seen timestamp
            skipped_count += 1
        else:
            # Parse posting_date — accept "YYYY-MM-DD" strings or None
            posting_date = job.get("posting_date")
            if isinstance(posting_date, str) and posting_date:
                try:
                    from datetime import date
                    posting_date = date.fromisoformat(posting_date[:10])
                except ValueError:
                    posting_date = None

            new_posting = JobPosting(
                content_hash=content_hash,
                title=job["title"],
                company=job["company"],
                location=job["location"],
                url=job.get("url", ""),
                source=job["source"],
                posting_date=posting_date,
                scraped_at=now,
                tags=job.get("tags", []),
                is_active=job.get("is_active", True),
            )
            db.add(new_posting)
            new_count += 1

    db.commit()

    logger.info(
        "upsert_complete",
        new=new_count,
        skipped_dupes=skipped_count,
        total=new_count + skipped_count,
    )
    return new_count, skipped_count
