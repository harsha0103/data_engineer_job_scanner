"""Parser for a single, user-supplied LinkedIn job posting URL.

LinkedIn publishes no job-search API or MCP server, and every third-party
"LinkedIn connector" works by automating a logged-in browser session — the
same kind of ToS-violating scraping this project has deliberately avoided
for LinkedIn from the start. So there is no search/bulk-fetch here.

What *is* fair game: LinkedIn serves its public /jobs/view/<id> pages without
login (confirmed directly — plain unauthenticated requests.get() returns full
title/company/location/description via server-rendered HTML, meant for SEO
and link-preview cards). Fetching the one URL a user explicitly pasted is not
meaningfully different from a human opening it in a browser — it's not search
automation. That's the boundary this module stays inside: one URL in, one job
record out, nothing more.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_JOB_ID_RE = re.compile(r"/jobs/view/(?:[^/]*-)?(\d{8,12})")
_RELATIVE_TIME_RE = re.compile(r"(\d+)\s+(hour|day|week|month)s?\s+ago", re.IGNORECASE)


def _extract(pattern: str, html: str) -> str | None:
    m = re.search(pattern, html, re.DOTALL)
    if not m:
        return None
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip()


def _parse_relative_posted(text: str | None) -> datetime | None:
    if not text:
        return None
    m = _RELATIVE_TIME_RE.search(text)
    if not m:
        return None
    amount, unit = int(m.group(1)), m.group(2).lower()
    delta = {
        "hour": timedelta(hours=amount),
        "day": timedelta(days=amount),
        "week": timedelta(weeks=amount),
        "month": timedelta(days=amount * 30),  # approximate, "months ago" has no exact form
    }[unit]
    return datetime.now(timezone.utc) - delta


def parse_job_url(url: str) -> dict[str, Any]:
    """Fetch one LinkedIn job posting URL and return upsert_job-shaped kwargs."""
    resp = requests.get(url, headers=_HEADERS, timeout=15, allow_redirects=True)

    if resp.status_code != 200 or "expired_jd_redirect" in resp.url:
        raise ValueError(f"LinkedIn job posting not available (expired or moved): {url}")

    html = resp.text
    job_id_match = _JOB_ID_RE.search(resp.url) or _JOB_ID_RE.search(url)
    if not job_id_match:
        raise ValueError(f"Could not find a job id in URL: {url}")

    title = _extract(r'top-card-layout__title[^>]*>(.*?)</h1>', html)
    company = _extract(r'topcard__org-name-link[^>]*>(.*?)</a>', html)
    location = _extract(r'topcard__flavor--bullet[^>]*>(.*?)</span>', html)
    description = _extract(r'show-more-less-html__markup[^>]*>(.*?)</div>', html)
    posted_text = _extract(r'posted-time-ago__text[^>]*>(.*?)</span>', html)

    if not title or not company or not description:
        raise ValueError(f"Could not parse expected fields from LinkedIn page: {url}")

    return {
        "external_id": job_id_match.group(1),
        "title": title,
        "company": company,
        "location": location,
        "remote_type": "remote" if location and "remote" in location.lower() else None,
        "description": description,
        "url": url,
        "posted_at": _parse_relative_posted(posted_text),
    }
