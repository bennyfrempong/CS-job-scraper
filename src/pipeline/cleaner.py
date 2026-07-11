"""
Field-level cleaner.

Normalizes raw job dicts before they enter the deduplication + DB layer.
Rules:
  - Strip HTML tags and excess whitespace from all text fields.
  - Apply sensible defaults for missing fields.
  - Hard-truncate to DB column maximums.
"""

import re
from typing import Dict, Any, Optional


def _strip_html(text: str) -> str:
    """Remove HTML tags with a lightweight regex (no BS4 dependency here)."""
    return re.sub(r"<[^>]+>", " ", text)


def _normalize_text(text: Optional[str], max_len: int = 500) -> str:
    """Strip HTML, collapse whitespace, enforce max length."""
    if not text:
        return ""
    cleaned = _strip_html(str(text))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_len]


def clean_job(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a raw job dict into a clean, consistent format.

    This runs BEFORE deduplication — the hash is computed on the cleaned values.
    """
    title = _normalize_text(raw.get("title"), 500) or "Software Intern"
    company = _normalize_text(raw.get("company"), 200) or "Unknown"
    location = _normalize_text(raw.get("location"), 200) or "Remote/Unknown"

    url = (raw.get("url") or "").strip()[:1000]
    source = (raw.get("source") or "unknown").strip().lower()[:50]

    tags = raw.get("tags") or []
    clean_tags = [t.strip().lower() for t in tags if isinstance(t, str) and t.strip()]

    return {
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "source": source,
        "posting_date": raw.get("posting_date"),
        "tags": list(dict.fromkeys(clean_tags))[:20],  # dedupe tags, preserve order
        "is_active": True,
    }
