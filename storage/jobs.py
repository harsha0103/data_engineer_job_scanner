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
) -> UUID:
    """Insert a job, or update it in place if (source_id, external_id) already exists.

    Re-running a scan over the same listing should update it, not duplicate it —
    that's what the schema's UNIQUE (source_id, external_id) constraint is for.
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
                RETURNING id
                """,
                (
                    source_id, external_id, title, company, location, remote_type,
                    salary_min, salary_max, description, url, posted_at,
                ),
            )
            job_id = cur.fetchone()[0]
    return job_id


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
