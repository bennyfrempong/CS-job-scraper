from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ── Database ────────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://pipeline_user:pipeline_pass@localhost:5432/jobpipeline"

    # ── Redis ───────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Optional API Keys (scrapers skip if absent) ─────────────────────────────
    ADZUNA_APP_ID: Optional[str] = None
    ADZUNA_APP_KEY: Optional[str] = None
    THE_MUSE_API_KEY: Optional[str] = None
    USAJOBS_API_KEY: Optional[str] = None
    USAJOBS_EMAIL: Optional[str] = None
    GITHUB_TOKEN: Optional[str] = None

    # ── Scraping Behaviour ──────────────────────────────────────────────────────
    REQUEST_DELAY_SECONDS: float = 1.0
    MAX_RETRIES: int = 3
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
