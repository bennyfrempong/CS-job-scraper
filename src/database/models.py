from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    DateTime, Date, JSON, UniqueConstraint, Index
)
from sqlalchemy.sql import func
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class JobPosting(Base):
    """A single deduplicated job/internship listing."""

    __tablename__ = "job_postings"

    id = Column(Integer, primary_key=True, index=True)
    content_hash = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(Text, nullable=False)
    company = Column(Text, nullable=False)
    location = Column(Text, default="Remote/Unknown")
    url = Column(Text)
    source = Column(String(50), nullable=False, index=True)
    posting_date = Column(Date, nullable=True)
    scraped_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    tags = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        Index("ix_job_postings_company", "company"),
        Index("ix_job_postings_scraped_at", "scraped_at"),
    )

    def __repr__(self) -> str:
        return f"<JobPosting id={self.id} title={self.title!r} company={self.company!r}>"


class ScrapeRun(Base):
    """One logged execution of a single scraper source."""

    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    new_listings = Column(Integer, default=0)
    skipped_dupes = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    # running | success | partial | failed | skipped
    status = Column(String(20), default="running")

    def __repr__(self) -> str:
        return f"<ScrapeRun id={self.id} source={self.source!r} status={self.status!r}>"


class ScrapeError(Base):
    """A single error event logged during a scrape run."""

    __tablename__ = "scrape_errors"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False, index=True)
    error_type = Column(Text)
    error_message = Column(Text)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<ScrapeError id={self.id} source={self.source!r} type={self.error_type!r}>"
