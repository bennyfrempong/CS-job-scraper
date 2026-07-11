"""Quick data preview — prints the 10 most recent listings from the DB."""
from src.database.session import SessionLocal
from src.database.models import JobPosting
from sqlalchemy import func

db = SessionLocal()
jobs = db.query(JobPosting).order_by(JobPosting.scraped_at.desc()).limit(10).all()

sep = "=" * 65
print(f"\n{sep}")
print("  Sample Listings from DB (10 most recent)")
print(sep)

for j in jobs:
    url = (j.url[:55] + "...") if len(j.url or "") > 55 else (j.url or "N/A")
    print(f"\n  [{j.source.upper()}]")
    print(f"  Title   : {j.title[:60]}")
    print(f"  Company : {j.company}")
    print(f"  Location: {j.location}")
    print(f"  URL     : {url}")

total = db.query(func.count(JobPosting.id)).scalar()
print(f"\n{sep}")
print(f"  Total unique listings in DB: {total}")
print(f"{sep}\n")
db.close()
