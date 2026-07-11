"""
Pytest fixtures shared across all test modules.

Uses SQLite (in-memory) so tests run without a live PostgreSQL instance.
The JSON column type is compatible with SQLite out of the box.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db():
    """
    Provide a fresh, isolated SQLite DB session for each test.

    Tables are created before the test and dropped after — complete isolation.
    """
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def sample_job() -> dict:
    """A canonical, fully-populated job dict for use in pipeline tests."""
    return {
        "title": "Software Engineering Intern",
        "company": "Acme Corp",
        "location": "San Francisco, CA",
        "url": "https://example.com/jobs/1",
        "source": "greenhouse",
        "posting_date": "2026-07-01",
        "tags": ["internship", "python", "backend"],
        "is_active": True,
    }


@pytest.fixture
def sample_raw_greenhouse() -> dict:
    """A realistic raw Greenhouse API response dict for one job."""
    return {
        "id": 123456,
        "title": "Software Engineering Intern - Summer 2026",
        "absolute_url": "https://boards.greenhouse.io/stripe/jobs/123456",
        "updated_at": "2026-06-15T12:00:00Z",
        "offices": [{"id": 1, "name": "Remote"}],
        "departments": [{"id": 10, "name": "Engineering"}],
        "_board_token": "stripe",
    }
