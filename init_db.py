"""
Local DB initializer — uses SQLAlchemy create_all() for SQLite compatibility.
For PostgreSQL (production), use: alembic upgrade head
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.utils.logger import setup_logging
from src.config import settings
from src.database.session import engine
from src.database.models import Base

setup_logging(settings.LOG_LEVEL)

print(f"Initializing database at: {settings.DATABASE_URL}")
Base.metadata.create_all(bind=engine)
print("Tables created: job_postings, scrape_runs, scrape_errors")
print("Done.")
