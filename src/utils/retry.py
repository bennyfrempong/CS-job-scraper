from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import requests
import logging
import structlog

logger = structlog.get_logger()
_std_logger = logging.getLogger(__name__)


def retry_with_backoff(max_attempts: int = 3):
    """
    Decorator factory for HTTP retries with exponential backoff.

    Retries on any requests.RequestException or TimeoutError.
    Delays: 2s → 4s → 8s.
    Logs a warning before each retry attempt.

    Usage:
        @retry_with_backoff(max_attempts=3)
        def fetch_data(): ...
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type(
            (requests.exceptions.RequestException, TimeoutError)
        ),
        before_sleep=before_sleep_log(_std_logger, logging.WARNING),
        reraise=True,
    )
