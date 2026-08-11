"""Filters and sorts search results by posting age, using a stricter cutoff
for well-known/large employers than for smaller or unrecognized ones.

Source-agnostic: takes get_company/get_posted_at extractor functions instead
of hardcoded field names, since Dice and Indeed use different shapes (Dice:
'companyName'/'postedDate' ISO string; Indeed: 'Company'/'Posted on' as
"July 02, 2026"). Each connector supplies its own extractors; this module
only deals in (company_name, parsed_datetime).

No source has a company-size signal of its own (confirmed for Dice by
calling get_company; Indeed's search results don't have one either) — so
BIG_COMPANIES is a manually maintained list, not a lookup. Note: many
postings, especially on Dice, come through staffing/recruiting agencies
rather than the direct employer — add recruiting firms you recognize if
that matters to your search.
"""

from datetime import datetime, timezone
from typing import Callable, TypeVar

T = TypeVar("T")

# Lowercased substrings matched against the company name. Edit freely.
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


def filter_by_recency(
    jobs: list[T],
    *,
    get_company: Callable[[T], str | None],
    get_posted_at: Callable[[T], datetime | None],
    big_company_window_days: float = 2,
    small_company_window_days: float = 1,
) -> list[T]:
    """Keep jobs posted within the recency window for their company's size.

    Recognized (big) companies: kept if posted within big_company_window_days.
    Everything else: kept only within small_company_window_days — smaller/
    unrecognized employers post rarely, so freshness matters more for them.
    Jobs with no parseable posted date are kept (can't judge age, don't discard).
    """
    today = datetime.now(timezone.utc).date()
    kept = []
    for job in jobs:
        posted_at = get_posted_at(job)
        if posted_at is None:
            kept.append(job)
            continue
        # Calendar-day difference, not exact-timestamp subtraction — Indeed
        # only gives day-granularity dates ("August 10, 2026", no time), so
        # comparing precise timestamps could count something posted "today"
        # as 1+ days old purely from UTC/local clock drift near midnight.
        # This also matches the plain-language "go back 2 days" framing.
        age_days = (today - posted_at.date()).days
        window = (
            big_company_window_days
            if _is_big_company(get_company(job))
            else small_company_window_days
        )
        if age_days <= window:
            kept.append(job)
    return kept


def sort_by_time_then_company(
    jobs: list[T],
    *,
    get_company: Callable[[T], str | None],
    get_posted_at: Callable[[T], datetime | None],
) -> list[T]:
    """Most recent first; ties broken alphabetically (A-Z) by company name.

    Two stable passes, since a single reverse=True sort on a tuple key would
    also flip company name to Z-A, which isn't what "ties broken A-Z" means.
    """
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    by_company = sorted(jobs, key=lambda j: get_company(j) or "")
    return sorted(by_company, key=lambda j: get_posted_at(j) or epoch, reverse=True)


# --- Dice-specific convenience wrappers (its shape is fixed and used a lot) ---


def _dice_posted_at(job: dict) -> datetime | None:
    posted = job.get("postedDate")
    if not posted:
        return None
    return datetime.fromisoformat(posted.replace("Z", "+00:00"))


def filter_dice_jobs(jobs: list[dict], **kwargs) -> list[dict]:
    return filter_by_recency(
        jobs, get_company=lambda j: j.get("companyName"), get_posted_at=_dice_posted_at, **kwargs
    )


def sort_dice_jobs(jobs: list[dict]) -> list[dict]:
    return sort_by_time_then_company(
        jobs, get_company=lambda j: j.get("companyName"), get_posted_at=_dice_posted_at
    )
