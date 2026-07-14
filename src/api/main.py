"""
Query API — Week 4 deliverable.

A read-only FastAPI service for browsing the scraped/deduplicated job
postings, plus operational visibility into scrape run health (useful for
demoing the "what happens when a source breaks" story in interviews).

Run locally:
    uvicorn src.api.main:app --reload

Endpoints:
    GET /health                     liveness check
    GET /postings                   list + filter + paginate postings
    GET /postings/{id}              single posting
    GET /stats                      overview counts (total, per-source, recent activity)
    GET /sources                    latest scrape_run status per source
    GET /sources/{name}/errors      recent errors logged for one source
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from src.database.session import get_db
from src.database.models import JobPosting, ScrapeRun, ScrapeError

app = FastAPI(
    title="CS Internship Job Pipeline API",
    description="Read-only query interface over scraped, deduplicated job postings.",
    version="1.0.0",
)

# Configure CORS for React frontend (Week 4)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def root():
    """Root endpoint for API liveness."""
    return {"message": "Job Scraper API is running. See /docs for endpoints."}


# ── Response schemas ─────────────────────────────────────────────────────────

class PostingOut(BaseModel):
    id: int
    title: str
    company: str
    location: str
    url: str
    source: str
    posting_date: Optional[date] = None
    scraped_at: datetime
    tags: List[str] = []
    is_active: bool

    model_config = {"from_attributes": True}


class PostingListOut(BaseModel):
    total: int
    limit: int
    offset: int
    results: List[PostingOut]


class SourceStatusOut(BaseModel):
    source: str
    status: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    new_listings: Optional[int] = None
    skipped_dupes: Optional[int] = None
    error_count: Optional[int] = None


class StatsOut(BaseModel):
    total_postings: int
    active_postings: int
    postings_last_24h: int
    postings_by_source: dict
    last_run_at: Optional[datetime] = None


class ScrapeErrorOut(BaseModel):
    id: int
    source: str
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    occurred_at: datetime

    model_config = {"from_attributes": True}


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/postings", response_model=PostingListOut)
def list_postings(
    db: Session = Depends(get_db),
    source: Optional[str] = Query(None, description="Filter by source, e.g. 'greenhouse'"),
    title: Optional[str] = Query(None, description="Case-insensitive partial match on job title/role"),
    company: Optional[str] = Query(None, description="Case-insensitive partial match"),
    location: Optional[str] = Query(None, description="Case-insensitive partial match"),
    tag: Optional[str] = Query(None, description="Filter postings containing this tag"),
    active_only: bool = Query(True, description="Only return is_active=True postings"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    q = db.query(JobPosting)

    if source:
        q = q.filter(JobPosting.source == source)
    if title:
        q = q.filter(JobPosting.title.ilike(f"%{title}%"))
    if company:
        q = q.filter(JobPosting.company.ilike(f"%{company}%"))
    if location:
        q = q.filter(JobPosting.location.ilike(f"%{location}%"))
    if active_only:
        q = q.filter(JobPosting.is_active.is_(True))
    if tag:
        # tags is a JSON list column — filter in Python for cross-DB compatibility
        # (SQLite has no native JSON containment operator; Postgres would use `@>`)
        candidates = q.all()
        filtered = [p for p in candidates if tag.lower() in [t.lower() for t in (p.tags or [])]]
        total = len(filtered)
        page = filtered[offset: offset + limit]
        return PostingListOut(total=total, limit=limit, offset=offset, results=page)

    total = q.count()
    results = (
        q.order_by(desc(JobPosting.scraped_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return PostingListOut(total=total, limit=limit, offset=offset, results=results)


@app.get("/postings/{posting_id}", response_model=PostingOut)
def get_posting(posting_id: int, db: Session = Depends(get_db)):
    posting = db.query(JobPosting).filter(JobPosting.id == posting_id).first()
    if not posting:
        raise HTTPException(status_code=404, detail="Posting not found")
    return posting


@app.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(JobPosting.id)).scalar() or 0
    active = (
        db.query(func.count(JobPosting.id))
        .filter(JobPosting.is_active.is_(True))
        .scalar()
        or 0
    )

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    last_24h = (
        db.query(func.count(JobPosting.id))
        .filter(JobPosting.scraped_at >= since)
        .scalar()
        or 0
    )

    by_source_rows = (
        db.query(JobPosting.source, func.count(JobPosting.id))
        .group_by(JobPosting.source)
        .all()
    )
    by_source = {source: count for source, count in by_source_rows}

    last_run = (
        db.query(func.max(ScrapeRun.completed_at))
        .scalar()
    )

    return StatsOut(
        total_postings=total,
        active_postings=active,
        postings_last_24h=last_24h,
        postings_by_source=by_source,
        last_run_at=last_run,
    )


@app.get("/sources", response_model=List[SourceStatusOut])
def list_sources(db: Session = Depends(get_db)):
    """Latest ScrapeRun per source — quick glance at pipeline health."""
    subq = (
        db.query(
            ScrapeRun.source,
            func.max(ScrapeRun.started_at).label("latest_start"),
        )
        .group_by(ScrapeRun.source)
        .subquery()
    )

    rows = (
        db.query(ScrapeRun)
        .join(
            subq,
            (ScrapeRun.source == subq.c.source)
            & (ScrapeRun.started_at == subq.c.latest_start),
        )
        .all()
    )

    return [
        SourceStatusOut(
            source=r.source,
            status=r.status,
            started_at=r.started_at,
            completed_at=r.completed_at,
            new_listings=r.new_listings,
            skipped_dupes=r.skipped_dupes,
            error_count=r.error_count,
        )
        for r in rows
    ]


@app.get("/sources/{name}/errors", response_model=List[ScrapeErrorOut])
def source_errors(name: str, limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    rows = (
        db.query(ScrapeError)
        .filter(ScrapeError.source == name)
        .order_by(desc(ScrapeError.occurred_at))
        .limit(limit)
        .all()
    )
    return rows
