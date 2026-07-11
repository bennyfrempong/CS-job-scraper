"""Dump the first 3000 chars of the README — emoji-safe."""
import requests
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/master/README.md"
resp = requests.get(url, timeout=15)
# Strip non-ASCII to avoid Windows cp1252 issues
text = resp.text[:3000].encode('ascii', errors='replace').decode('ascii')
print(text)
