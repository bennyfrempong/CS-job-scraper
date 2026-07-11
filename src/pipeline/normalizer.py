"""
Pandas-based schema normalizer.

Runs after clean_job() to enforce column types and fill any remaining gaps
across an entire batch of jobs in one vectorized pass.
"""

from typing import List, Dict, Any

import pandas as pd

# The canonical column set that the DB expects
SCHEMA_COLUMNS = [
    "title",
    "company",
    "location",
    "url",
    "source",
    "posting_date",
    "tags",
    "is_active",
]

DEFAULTS: Dict[str, Any] = {
    "title": "Software Intern",
    "company": "Unknown",
    "location": "Remote/Unknown",
    "url": "",
    "source": "unknown",
    "posting_date": None,
    "tags": None,      # handled separately to avoid mutable default
    "is_active": True,
}


def normalize_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Accept a list of cleaned job dicts and return them schema-enforced.

    - Adds any missing columns with sensible defaults.
    - Ensures tags is always a list (never None / NaN).
    - Drops any extra keys not in SCHEMA_COLUMNS.
    - Returns an empty list if input is empty.
    """
    if not jobs:
        return []

    df = pd.DataFrame(jobs)

    # Add any missing columns
    for col, default in DEFAULTS.items():
        if col not in df.columns:
            df[col] = default

    # Select and order to schema
    df = df[SCHEMA_COLUMNS].copy()

    # Fill per-column defaults
    df["title"] = df["title"].fillna("Software Intern")
    df["company"] = df["company"].fillna("Unknown")
    df["location"] = df["location"].fillna("Remote/Unknown")
    df["url"] = df["url"].fillna("")
    df["source"] = df["source"].fillna("unknown")
    df["is_active"] = df["is_active"].fillna(True).astype(bool)

    # tags must always be a plain Python list — NaN / None → []
    df["tags"] = df["tags"].apply(
        lambda x: x if isinstance(x, list) else []
    )

    return df.to_dict("records")
