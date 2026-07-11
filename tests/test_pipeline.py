"""
Tests for the pipeline layer: cleaner, normalizer, deduplicator.
Run with: pytest tests/test_pipeline.py -v
"""
import pytest
from src.pipeline.cleaner import clean_job
from src.pipeline.normalizer import normalize_jobs
from src.pipeline.deduplicator import compute_hash, upsert_jobs
from src.database.models import JobPosting


# ── Cleaner tests ────────────────────────────────────────────────────────────

class TestCleaner:
    def test_strips_html_tags(self):
        raw = {"title": "<b>Software Intern</b>", "company": "Acme", "source": "test"}
        result = clean_job(raw)
        assert "<b>" not in result["title"]
        assert "Software Intern" in result["title"]

    def test_collapses_whitespace(self):
        raw = {"title": "  Software   Intern  ", "company": "Acme", "source": "test"}
        result = clean_job(raw)
        assert result["title"] == "Software Intern"

    def test_defaults_missing_title(self):
        result = clean_job({"company": "Acme", "source": "test"})
        assert result["title"] == "Software Intern"

    def test_defaults_missing_company(self):
        result = clean_job({"title": "SWE Intern", "source": "test"})
        assert result["company"] == "Unknown"

    def test_defaults_missing_location(self):
        result = clean_job({"title": "SWE Intern", "company": "Acme", "source": "test"})
        assert result["location"] == "Remote/Unknown"

    def test_dedupes_tags(self):
        raw = {"title": "Intern", "company": "X", "source": "test",
               "tags": ["python", "python", "backend"]}
        result = clean_job(raw)
        assert result["tags"].count("python") == 1

    def test_truncates_long_title(self):
        raw = {"title": "A" * 600, "company": "X", "source": "test"}
        result = clean_job(raw)
        assert len(result["title"]) <= 500


# ── Normalizer tests ─────────────────────────────────────────────────────────

class TestNormalizer:
    def test_empty_input_returns_empty(self):
        assert normalize_jobs([]) == []

    def test_adds_missing_columns(self):
        jobs = [{"title": "SWE Intern", "company": "Acme", "source": "test"}]
        result = normalize_jobs(jobs)
        assert "location" in result[0]
        assert "tags" in result[0]
        assert "is_active" in result[0]

    def test_tags_always_list(self):
        jobs = [{"title": "SWE Intern", "company": "Acme", "source": "test", "tags": None}]
        result = normalize_jobs(jobs)
        assert isinstance(result[0]["tags"], list)

    def test_drops_extra_keys(self):
        jobs = [{"title": "SWE Intern", "company": "Acme", "source": "test",
                 "extra_garbage_field": "should_be_gone"}]
        result = normalize_jobs(jobs)
        assert "extra_garbage_field" not in result[0]

    def test_handles_multiple_jobs(self, sample_job):
        jobs = [sample_job, {**sample_job, "company": "Beta Corp"}]
        result = normalize_jobs(jobs)
        assert len(result) == 2


# ── Deduplicator tests ───────────────────────────────────────────────────────

class TestDeduplicator:
    def test_hash_is_deterministic(self):
        h1 = compute_hash("SWE Intern", "Acme", "Remote")
        h2 = compute_hash("SWE Intern", "Acme", "Remote")
        assert h1 == h2

    def test_hash_is_case_insensitive(self):
        h1 = compute_hash("SWE Intern", "Acme", "Remote")
        h2 = compute_hash("swe intern", "ACME", "REMOTE")
        assert h1 == h2

    def test_hash_differs_on_different_fields(self):
        h1 = compute_hash("SWE Intern", "Acme", "Remote")
        h2 = compute_hash("Data Intern", "Acme", "Remote")
        assert h1 != h2

    def test_hash_is_64_chars(self):
        h = compute_hash("SWE Intern", "Acme", "Remote")
        assert len(h) == 64

    def test_new_job_is_inserted(self, db, sample_job):
        new, skipped = upsert_jobs([sample_job], db)
        assert new == 1
        assert skipped == 0
        assert db.query(JobPosting).count() == 1

    def test_duplicate_is_skipped(self, db, sample_job):
        upsert_jobs([sample_job], db)
        new, skipped = upsert_jobs([sample_job], db)
        assert new == 0
        assert skipped == 1
        assert db.query(JobPosting).count() == 1  # still only 1 row

    def test_within_batch_duplicate_is_skipped(self, db, sample_job):
        """Two identical jobs in the same batch should produce only 1 DB row."""
        new, skipped = upsert_jobs([sample_job, sample_job], db)
        assert new == 1
        assert skipped == 1
        assert db.query(JobPosting).count() == 1

    def test_different_jobs_both_inserted(self, db, sample_job):
        job2 = {**sample_job, "company": "Beta Corp"}
        new, skipped = upsert_jobs([sample_job, job2], db)
        assert new == 2
        assert skipped == 0


# ── Scraper parse tests ──────────────────────────────────────────────────────

class TestGreenhouseParse:
    def test_parse_returns_required_fields(self, sample_raw_greenhouse):
        from src.scrapers.greenhouse import GreenhouseScraper
        scraper = GreenhouseScraper()
        result = scraper.parse(sample_raw_greenhouse)
        for field in ("title", "company", "location", "url", "source", "tags"):
            assert field in result, f"Missing field: {field}"

    def test_parse_sets_source(self, sample_raw_greenhouse):
        from src.scrapers.greenhouse import GreenhouseScraper
        result = GreenhouseScraper().parse(sample_raw_greenhouse)
        assert result["source"] == "greenhouse"

    def test_parse_extracts_location(self, sample_raw_greenhouse):
        from src.scrapers.greenhouse import GreenhouseScraper
        result = GreenhouseScraper().parse(sample_raw_greenhouse)
        assert result["location"] == "Remote"

    def test_parse_includes_internship_tag(self, sample_raw_greenhouse):
        from src.scrapers.greenhouse import GreenhouseScraper
        result = GreenhouseScraper().parse(sample_raw_greenhouse)
        assert "internship" in result["tags"]
