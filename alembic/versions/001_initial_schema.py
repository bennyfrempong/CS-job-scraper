"""Initial schema — creates job_postings, scrape_runs, scrape_errors.

Revision ID: 001
Revises:
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── job_postings ──────────────────────────────────────────────────────────
    op.create_table(
        "job_postings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("posting_date", sa.Date(), nullable=True),
        sa.Column(
            "scraped_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_hash", name="uq_job_postings_content_hash"),
    )
    op.create_index("ix_job_postings_id", "job_postings", ["id"])
    op.create_index("ix_job_postings_content_hash", "job_postings", ["content_hash"], unique=True)
    op.create_index("ix_job_postings_source", "job_postings", ["source"])
    op.create_index("ix_job_postings_company", "job_postings", ["company"])
    op.create_index("ix_job_postings_scraped_at", "job_postings", ["scraped_at"])

    # ── scrape_runs ───────────────────────────────────────────────────────────
    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("new_listings", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("skipped_dupes", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("error_count", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("status", sa.String(20), nullable=True, server_default=sa.text("'running'")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scrape_runs_id", "scrape_runs", ["id"])
    op.create_index("ix_scrape_runs_source", "scrape_runs", ["source"])

    # ── scrape_errors ─────────────────────────────────────────────────────────
    op.create_table(
        "scrape_errors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("error_type", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scrape_errors_id", "scrape_errors", ["id"])
    op.create_index("ix_scrape_errors_source", "scrape_errors", ["source"])


def downgrade() -> None:
    op.drop_table("scrape_errors")
    op.drop_table("scrape_runs")
    op.drop_table("job_postings")
