"""Client for Dice's public MCP server.

No auth required. Confirmed against the live server at https://mcp.dice.com/mcp
(see docs.dice.com career-advice guide) — three tools: search_jobs, get_job_details,
get_company. Every function here returns the tool's raw structured_content payload;
turning that into an `embedd.jobs` row is the storage layer's job, not this one.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

DICE_MCP_URL = "https://mcp.dice.com/mcp"


@asynccontextmanager
async def _dice_session():
    async with streamable_http_client(DICE_MCP_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    # Drop unset optional params instead of sending explicit nulls — the schema
    # types them as e.g. "string", not "string|null", so omission is the safe form.
    arguments = {k: v for k, v in arguments.items() if v is not None}
    async with _dice_session() as session:
        result = await session.call_tool(name, arguments)
        if result.is_error:
            raise RuntimeError(f"Dice MCP tool '{name}' returned an error: {result.content}")
        return result.structured_content


async def search_jobs(
    keyword: str,
    *,
    location: str | None = None,
    jobs_per_page: int = 25,
    page_number: int = 1,
    posted_date: str | None = None,  # 'ONE' | 'THREE' | 'SEVEN'
    workplace_types: list[str] | None = None,  # 'Remote' | 'On-Site' | 'Hybrid'
) -> dict[str, Any]:
    """Search Dice job listings. Returns {'data': [...], 'metadata': {...}}.

    Each item's 'guid' (not 'id') is what get_job_details/get_company expect.
    """
    return await _call_tool(
        "search_jobs",
        {
            "keyword": keyword,
            "location": location,
            "jobs_per_page": jobs_per_page,
            "page_number": page_number,
            "posted_date": posted_date,
            "workplace_types": workplace_types,
        },
    )


async def get_job_details(job_id: str) -> dict[str, Any]:
    """Full description + skills for one job. job_id is the 'guid' from search_jobs."""
    return await _call_tool("get_job_details", {"job_id": job_id})


async def get_company(job_id: str) -> dict[str, Any]:
    """Company info for the employer behind one job. job_id is the 'guid' from search_jobs."""
    return await _call_tool("get_company", {"job_id": job_id})


def to_job_record(listing: dict[str, Any], description: str) -> dict[str, Any]:
    """Map a search_jobs listing + its full description to upsert_job kwargs."""
    posted = listing.get("postedDate")
    location = listing.get("jobLocation") or {}

    return {
        "external_id": listing["guid"],
        "title": listing["title"],
        "company": listing["companyName"],
        "location": location.get("displayName"),
        "remote_type": "remote" if listing.get("isRemote") else None,
        "description": description,
        "url": listing["detailsPageUrl"],
        "posted_at": datetime.fromisoformat(posted.replace("Z", "+00:00")) if posted else None,
    }
