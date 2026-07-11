"""
Celery application and Beat schedule configuration.

Broker + backend: Upstash Redis (TLS — rediss:// URL)
Schedule: run_all_scrapers every 6 hours

Starting the worker (Windows — must use solo pool):
    celery -A src.tasks.celery_app worker --loglevel=info --pool=solo

Starting the beat scheduler (separate terminal):
    celery -A src.tasks.celery_app beat --loglevel=info

Or combine both in one process for development:
    celery -A src.tasks.celery_app worker --beat --loglevel=info --pool=solo
"""

from celery import Celery
from celery.schedules import crontab

from src.config import settings

app = Celery(
    "jobpipeline",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["src.tasks.scrape_tasks"],
)

# ── Serialization ────────────────────────────────────────────────────────────
app.conf.task_serializer = "json"
app.conf.result_serializer = "json"
app.conf.accept_content = ["json"]
app.conf.timezone = "UTC"
app.conf.enable_utc = True

# ── Upstash SSL (rediss://) ──────────────────────────────────────────────────
# Upstash uses valid TLS certs — no ssl_cert_reqs override needed.
# The double-s in rediss:// enables SSL automatically in redis-py.
app.conf.broker_transport_options = {
    "socket_timeout": 10,
    "socket_connect_timeout": 10,
    "retry_on_timeout": True,
}
app.conf.result_backend_transport_options = {
    "socket_timeout": 10,
    "retry_on_timeout": True,
}

# ── Task behaviour ───────────────────────────────────────────────────────────
app.conf.task_acks_late = True          # re-queue on worker crash
app.conf.task_reject_on_worker_lost = True
app.conf.worker_prefetch_multiplier = 1  # one task at a time per worker
app.conf.task_time_limit = 600          # hard kill after 10 minutes
app.conf.task_soft_time_limit = 540     # soft warning at 9 minutes

# ── Beat schedule ────────────────────────────────────────────────────────────
app.conf.beat_schedule = {
    # Run all 10 scrapers every 6 hours
    "scrape-all-6h": {
        "task": "scrape.all",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    # Run SimplifyJobs daily (the repo updates once a day)
    "scrape-simplifyjobs-daily": {
        "task": "scrape.simplifyjobs",
        "schedule": crontab(minute=30, hour=8),  # 8:30 UTC
    },
}
