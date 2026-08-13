"""Insert/query functions for embedd.jobs — deduped on (source_id, external_id)."""

from datetime import datetime
from uuid import UUID

from .connection import get_connection


def upsert_job(
    *,
    source_id: int,
    external_id: str,
    title: str,
    company: str,
    description: str,
    url: str,
    location: str | None = None,
    remote_type: str | None = None,
    salary_min: float | None = None,
    salary_max: float | None = None,
    posted_at: datetime | None = None,
) -> tuple[UUID, bool]:
    """Insert a job, or update it in place if (source_id, external_id) already exists.

    Re-running a scan over the same listing should update it, not duplicate it —
    that's what the schema's UNIQUE (source_id, external_id) constraint is for.

    Returns (job_id, was_new) — was_new distinguishes a fresh insert from an
    update to an existing row (via Postgres's xmax=0 trick), so callers doing
    scan_runs bookkeeping can tell jobs_found apart from jobs_new.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO embedd.jobs (
                    source_id, external_id, title, company, location, remote_type,
                    salary_min, salary_max, description, url, posted_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_id, external_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    company = EXCLUDED.company,
                    location = EXCLUDED.location,
                    remote_type = EXCLUDED.remote_type,
                    salary_min = EXCLUDED.salary_min,
                    salary_max = EXCLUDED.salary_max,
                    description = EXCLUDED.description,
                    url = EXCLUDED.url,
                    posted_at = EXCLUDED.posted_at
                RETURNING id, (xmax = 0) AS was_new
                """,
                (
                    source_id, external_id, title, company, location, remote_type,
                    salary_min, salary_max, description, url, posted_at,
                ),
            )
            job_id, was_new = cur.fetchone()
    return job_id, was_new


def get_jobs_missing_score() -> list[dict]:
    """Jobs with no embedd.job_scores row yet — for the rubric scorer, which
    doesn't need description_embedding, just the raw description text."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT j.id, j.title, j.company, j.location, j.description
                FROM embedd.jobs j
                LEFT JOIN embedd.job_scores js ON js.job_id = j.id
                WHERE js.job_id IS NULL
                """
            )
            rows = cur.fetchall()
            columns = [d.name for d in cur.description]
    return [dict(zip(columns, row)) for row in rows]


def get_jobs_missing_embedding() -> list[dict]:
    """Jobs that still need their description_embedding computed and stored."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, description FROM embedd.jobs
                WHERE description_embedding IS NULL
                """
            )
            rows = cur.fetchall()
            columns = [d.name for d in cur.description]
    return [dict(zip(columns, row)) for row in rows]


def update_embedding(job_id: UUID, embedding: list[float]) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE embedd.jobs SET description_embedding = %s WHERE id = %s",
                (embedding, job_id),
            )


def get_jobs_ranked_by_fit(resume_embedding: list[float], max_age_days: int = 2) -> list[dict]:
    """Every embedded job posted within max_age_days. Sorted with not_applied
    jobs first (that's the point — those are the ones still needing a look),
    then everything you've already acted on (applied, not_interested, etc.)
    pushed below; fit score breaks ties within each group. Jobs with no
    embedding yet are excluded — nothing to rank them against. Jobs with no
    posted_at (unparseable date) are kept — can't judge their age, don't hide
    them."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT j.id, j.title, j.company, j.location, j.url, j.posted_at,
                       s.name AS source,
                       1 - (j.description_embedding <=> %(resume_embedding)s::vector) AS fit_score,
                       COALESCE(a.status, 'not_applied') AS status,
                       js.overall_score, js.skills_match, js.level_match,
                       js.location_match, js.comp_match, js.notes AS score_notes
                FROM embedd.jobs j
                JOIN embedd.sources s ON s.id = j.source_id
                LEFT JOIN embedd.applications a ON a.job_id = j.id
                LEFT JOIN embedd.job_scores js ON js.job_id = j.id
                WHERE j.description_embedding IS NOT NULL
                  AND (j.posted_at IS NULL OR j.posted_at >= now() - %(max_age_days)s * INTERVAL '1 day')
                ORDER BY (COALESCE(a.status, 'not_applied') != 'not_applied'),
                         j.description_embedding <=> %(resume_embedding)s::vector
                """,
                {"resume_embedding": resume_embedding, "max_age_days": max_age_days},
            )
            rows = cur.fetchall()
            columns = [d.name for d in cur.description]
    return [dict(zip(columns, row)) for row in rows]


def get_job(job_id: UUID) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source_id, external_id, title, company, location,
                       remote_type, salary_min, salary_max, description, url,
                       posted_at, scraped_at
                FROM embedd.jobs WHERE id = %s
                """,
                (job_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            columns = [d.name for d in cur.description]
    return dict(zip(columns, row))
