"""Runs the multi-title job search sweep and stores results.

Dice runs entirely in Python (search -> recency filter -> full details ->
store). Indeed can't: its connector only works inside a Claude session
(established earlier — no standalone client exists), so Indeed's half of the
sweep is fetched live by Claude calling its own tools, then handed to
store_indeed_search() / store_indeed_details() here for parsing + storage.
Both halves land in the same embedd.jobs table either way.
"""

from typing import Any

from connectors import dice
from connectors import indeed as indeed_parser
from storage.jobs import upsert_job
from storage.scan_runs import finish_run, start_run
from storage.sources import get_source_id

from .recency_filter import filter_by_recency, filter_dice_jobs, sort_dice_jobs

SEARCH_TERMS = [
    "Data Engineer",
    "Senior Data Engineer",
    "Lead Data Engineer",
    "Big Data Engineer",
    "Spark Developer",
    "AI Engineer",
]


async def run_dice_sweep(
    terms: list[str] = SEARCH_TERMS, jobs_per_page: int = 10
) -> list[dict[str, Any]]:
    """Search Dice for each term, keep only recent-enough listings, store them."""
    source_id = get_source_id("dice")
    run_id = start_run(source_id)
    stored: list[dict[str, Any]] = []
    seen_guids: set[str] = set()
    jobs_new = 0

    try:
        for term in terms:
            results = await dice.search_jobs(term, jobs_per_page=jobs_per_page)
            listings = sort_dice_jobs(results["data"])
            listings = filter_dice_jobs(listings)

            for listing in listings:
                guid = listing["guid"]
                if guid in seen_guids:
                    continue
                seen_guids.add(guid)

                details = await dice.get_job_details(guid)
                record = dice.to_job_record(listing, details["description"])
                job_id, was_new = upsert_job(source_id=source_id, **record)
                jobs_new += was_new
                stored.append({"job_id": job_id, "source": "dice", "term": term, **record})
    except Exception:
        finish_run(run_id, jobs_found=len(stored), jobs_new=jobs_new, status="failed")
        raise

    finish_run(run_id, jobs_found=len(stored), jobs_new=jobs_new, status="success")
    return stored


def filter_indeed_listings(listings: list[dict[str, str]]) -> list[dict[str, str]]:
    """Apply the same recency rule to parsed Indeed listings as Dice gets."""
    return filter_by_recency(
        listings,
        get_company=lambda l: l.get("Company"),
        get_posted_at=lambda l: indeed_parser.parse_posted_date(l.get("Posted on")),
    )


def store_indeed_job(listing: dict[str, str], details_markdown: str) -> dict[str, Any]:
    """listing: one item from indeed_parser.parse_search_results().
    details_markdown: raw get_job_details output, fetched live for this listing.
    """
    details = indeed_parser.parse_job_details(details_markdown)
    record = indeed_parser.to_job_record(listing, details["Description"])
    source_id = get_source_id("indeed")
    job_id, was_new = upsert_job(source_id=source_id, **record)
    return {"job_id": job_id, "was_new": was_new, "source": "indeed", **record}


def start_indeed_sweep() -> Any:
    """Indeed has no single Python-owned loop (Claude drives the tool calls
    live) — so the run is started/finished explicitly around that sequence,
    instead of implicitly like run_dice_sweep does."""
    return start_run(get_source_id("indeed"))


def finish_indeed_sweep(run_id: Any, stored: list[dict[str, Any]], status: str = "success") -> None:
    jobs_new = sum(1 for j in stored if j.get("was_new"))
    finish_run(run_id, jobs_found=len(stored), jobs_new=jobs_new, status=status)
