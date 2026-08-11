"""Parser for Indeed job data — NOT a network client.

Indeed's own docs restrict their MCP server to "Claude Connector" only (confirmed
directly against docs.indeed.com) — there is no endpoint a standalone script can
call. The only way to fetch Indeed data is a Claude session (interactive, or later
a scheduled agent) calling its built-in Indeed connector tools, which return
formatted markdown text rather than structured JSON like Dice does.

So this module's job starts *after* that fetch: parse that markdown into the same
shape storage.jobs.upsert_job expects, so storage doesn't care which board a job
came from.

IMPORTANT — external_id: Indeed's own `Job Id` (e.g. "JOBSEARCH_37") and its
"View Job URL" are per-request tokens, not stable identifiers — confirmed
empirically by running the identical search twice and seeing both change for the
same listing, while title/company/location/posted-date stayed identical. So
external_id here is a hash of those stable content fields instead, not anything
Indeed itself hands back.
"""

import hashlib
import re
from datetime import datetime
from typing import Any

_HEADER_LABELS = {
    "Job Title",
    "View Job URL",
    "Job Id",
    "Company",
    "Location",
    "Posted on",
    "Job Type",
    "Compensation",
}


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return None if value in ("", "N/A", "None") else value


def _parse_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block.splitlines():
        m = re.match(r"\s*\*\*([^*:]+):\*\*\s*(.*)", line)
        if m:
            fields[m.group(1).strip()] = m.group(2).strip()
    return fields


def parse_search_results(markdown: str) -> list[dict[str, str]]:
    """Parse search_jobs' markdown into a list of raw field dicts, one per listing."""
    blocks = re.split(r"\n\s*\n", markdown.strip())
    listings = []
    for block in blocks:
        fields = _parse_fields(block)
        if "Job Title" in fields:
            listings.append(fields)
    return listings


def parse_job_details(markdown: str) -> dict[str, str]:
    """Parse get_job_details' markdown into raw fields plus a 'Description' body."""
    lines = markdown.strip().splitlines()
    fields: dict[str, str] = {}

    if lines:
        title_match = re.match(r"#{1,6}\s*(.+)", lines[0])
        if title_match:
            fields["Job Title"] = title_match.group(1).strip()
            lines = lines[1:]

    body_start = len(lines)
    for i, line in enumerate(lines):
        m = re.match(r"\s*\*\*([^*:]+):\*\*\s*(.*)", line)
        if m and m.group(1).strip() in _HEADER_LABELS:
            fields[m.group(1).strip()] = m.group(2).strip()
        elif line.strip() == "":
            continue
        else:
            body_start = i
            break

    fields["Description"] = "\n".join(lines[body_start:]).strip()
    return fields


def make_external_id(title: str, company: str, location: str, posted_on: str) -> str:
    raw = f"{title}|{company}|{location}|{posted_on}".lower().strip()
    return hashlib.sha256(raw.encode()).hexdigest()


def _parse_posted_date(posted_on: str | None) -> datetime | None:
    posted_on = _clean(posted_on)
    if posted_on is None:
        return None
    try:
        return datetime.strptime(posted_on, "%B %d, %Y")
    except ValueError:
        return None


def to_job_record(listing: dict[str, str], description: str) -> dict[str, Any]:
    """Map a parsed search-result listing + its full description to upsert_job kwargs."""
    title = listing["Job Title"]
    company = listing["Company"]
    location = _clean(listing.get("Location"))
    posted_on = listing.get("Posted on")

    return {
        "external_id": make_external_id(title, company, location or "", posted_on or ""),
        "title": title,
        "company": company,
        "location": location,
        "remote_type": "remote" if location and "remote" in location.lower() else None,
        "description": description,
        "url": listing["View Job URL"],
        "posted_at": _parse_posted_date(posted_on),
        # salary parsing skipped for now — Compensation is free text ("$60 - $70
        # an hour" vs "$165,000 - $180,000 a year" vs "N/A"), same limitation as
        # Dice's salary field. Not worth the parsing complexity until something
        # downstream actually needs salary_min/salary_max populated.
    }
