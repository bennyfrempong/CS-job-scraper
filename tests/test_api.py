import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from src.api.main import app
from src.database.session import get_db, SessionLocal
from src.database.models import JobPosting, ScrapeRun, Base
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

# In-memory SQLite for testing the API
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = SessionLocal

# Create tables in test DB
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        # Bind to our test engine instead of the default one
        db.bind = engine
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.bind = engine
    
    # Insert some dummy data
    job1 = JobPosting(
        content_hash="hash1",
        title="Software Engineer Intern",
        company="TechCorp",
        location="Remote",
        url="https://techcorp.com/jobs/1",
        source="simplifyjobs",
        scraped_at=datetime.now(timezone.utc),
        is_active=True,
        tags=["internship", "simplifyjobs"]
    )
    job2 = JobPosting(
        content_hash="hash2",
        title="Data Science Intern",
        company="DataInc",
        location="New York, NY",
        url="https://datainc.com/intern",
        source="themuse",
        scraped_at=datetime.now(timezone.utc),
        is_active=True,
        tags=["internship", "data"]
    )
    
    run1 = ScrapeRun(
        source="simplifyjobs",
        status="success",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        new_listings=10
    )
    
    db.add(job1)
    db.add(job2)
    db.add(run1)
    db.commit()
    db.close()

def test_read_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_read_stats():
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_postings"] == 2
    assert data["active_postings"] == 2
    assert "simplifyjobs" in data["postings_by_source"]
    assert data["postings_by_source"]["simplifyjobs"] == 1

def test_read_postings():
    response = client.get("/postings")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["results"]) == 2

def test_filter_postings_by_source():
    response = client.get("/postings?source=themuse")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["results"][0]["company"] == "DataInc"

def test_search_postings_by_title():
    response = client.get("/postings?title=data")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["results"][0]["title"] == "Data Science Intern"

def test_read_single_posting():
    # Find the job ID first
    jobs_response = client.get("/postings")
    job_id = jobs_response.json()["results"][0]["id"]
    
    response = client.get(f"/postings/{job_id}")
    assert response.status_code == 200
    assert response.json()["id"] == job_id

def test_read_sources():
    response = client.get("/sources")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["source"] == "simplifyjobs"
    assert data[0]["status"] == "success"
    assert data[0]["new_listings"] == 10
