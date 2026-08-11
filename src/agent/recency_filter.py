"""Filters and sorts Dice search results by posting age, using a stricter
cutoff for well-known/large employers than for smaller or unrecognized ones.

Dice's API has no company-size signal of its own — search_jobs doesn't return
employee count or revenue, and get_company only returns name/desc/message
(confirmed by calling it) — so BIG_COMPANIES is a manually maintained list,
not a lookup. Note: many Dice postings come through staffing/recruiting
agencies rather than the direct employer, so `companyName` is often the
staffer's name, not the end client — add recruiting firms you recognize if
that matters to your search.
"""

from datetime import datetime, timezone
from typing import Any

# Lowercased substrings matched against companyName. Edit freely.
BIG_COMPANIES: set[str] = {
    "google",
    "amazon",
    "microsoft",
    "meta",
    "apple",
    "netflix",
    "salesforce",
    "oracle",
    "ibm",
    "jpmorgan",
    "capital one",
    "walmart",
}


def _is_big_company(company_name: str | None) -> bool:
    if not company_name:
        return False
    name = company_name.lower()
    return any(big in name for big in BIG_COMPANIES)


def _posted_days_ago(posted_date: str | None) -> float | None:
    if not posted_date:
        return None
    posted = datetime.fromisoformat(posted_date.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - posted).total_seconds() / 86400


def filter_by_recency(
    jobs: list[dict[str, Any]],
    *,
    big_company_window_days: float = 2,
    small_company_window_days: float = 1,
) -> list[dict[str, Any]]:
    """Keep jobs posted within the recency window for their company's size.

    Recognized (big) companies: kept if posted within big_company_window_days.
    Everything else: kept only within small_company_window_days — smaller/
    unrecognized employers post rarely, so freshness matters more for them.
    Jobs with no parseable postedDate are kept (can't judge age, don't discard).
    """
    kept = []
    for job in jobs:
        age_days = _posted_days_ago(job.get("postedDate"))
        if age_days is None:
            kept.append(job)
            continue
        window = (
            big_company_window_days
            if _is_big_company(job.get("companyName"))
            else small_company_window_days
        )
        if age_days <= window:
            kept.append(job)
    return kept


def sort_by_time_then_company(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Most recent first; ties broken alphabetically (A-Z) by company name.

    Two stable passes, since a single reverse=True sort on a tuple key would
    also flip company name to Z-A, which isn't what "ties broken A-Z" means.
    """
    by_company = sorted(jobs, key=lambda j: j.get("companyName") or "")
    return sorted(by_company, key=lambda j: j.get("postedDate") or "", reverse=True)
