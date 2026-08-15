"""Daily local automation: Dice sweep -> embed new jobs -> score new jobs.

Indeed is NOT run here — its connector only works inside a live Claude
session's MCP tools (established repeatedly: Indeed restricts their MCP
server to Claude Connector only), which a scheduled local script isn't.
Run an Indeed sweep periodically yourself in a Claude Code session instead;
it lands in the same tables this script reads/writes.

Scheduled via launchd (see scripts/setup_launchd.sh). Run manually with:
    uv run python main.py
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from agent.scorer import score_job
from agent.search_sweep import run_dice_sweep
from embedding.openai_embeddings import embed_text
from storage.jobs import delete_stale_jobs, get_jobs_missing_embedding, get_jobs_missing_score, update_embedding
from storage.resume import get_base_resume
from storage.scores import upsert_score


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC] {msg}", flush=True)


async def main() -> None:
    log("starting daily sweep")

    stored = await run_dice_sweep()
    log(f"Dice sweep: {len(stored)} jobs stored")

    missing_embedding = get_jobs_missing_embedding()
    for job in missing_embedding:
        vec = embed_text(job["description"])
        update_embedding(job["id"], vec)
    log(f"embedded {len(missing_embedding)} jobs")

    resume = get_base_resume()
    if resume is None:
        log("no base resume found — skipping scoring")
    else:
        unscored = get_jobs_missing_score()
        for job in unscored:
            result = score_job(resume["resume_text"], job["title"], job["company"], job["location"], job["description"])
            upsert_score(
                job["id"],
                overall_score=result.overall_score,
                skills_match=result.skills_match,
                level_match=result.level_match,
                location_match=result.location_match,
                comp_match=result.comp_match,
                notes=result.notes,
            )
        log(f"scored {len(unscored)} jobs")

    deleted = delete_stale_jobs(max_age_days=30)
    log(f"deleted {deleted} stale (30+ day old, never-applied-to) jobs")

    log("daily sweep complete")


if __name__ == "__main__":
    asyncio.run(main())
