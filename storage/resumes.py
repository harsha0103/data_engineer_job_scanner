"""Storage for embedd.resumes — generated tailored resume files, one row per job."""

from uuid import UUID

from .connection import get_connection


def insert_resume(job_id: UUID, file_path: str, summary_of_changes: str) -> UUID:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO embedd.resumes (job_id, file_path, summary_of_changes)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (job_id, file_path, summary_of_changes),
            )
            resume_id = cur.fetchone()[0]
    return resume_id


def get_resume_for_job(job_id: UUID) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, file_path, summary_of_changes, generated_at
                FROM embedd.resumes WHERE job_id = %s
                ORDER BY generated_at DESC LIMIT 1
                """,
                (job_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            columns = [d.name for d in cur.description]
    return dict(zip(columns, row))


def get_latest_resumes_for_jobs(job_ids: list[UUID]) -> dict[UUID, dict]:
    """Batched form of get_resume_for_job — one query for every job in the
    list instead of one query per job. Streamlit's job list calls this once
    per page render for potentially dozens of jobs; doing that as N separate
    queries is the N+1 pattern that made the page unusable once the database
    stopped being on localhost."""
    if not job_ids:
        return {}
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (job_id) job_id, id, file_path, summary_of_changes, generated_at
                FROM embedd.resumes
                WHERE job_id = ANY(%s)
                ORDER BY job_id, generated_at DESC
                """,
                (job_ids,),
            )
            rows = cur.fetchall()
            columns = [d.name for d in cur.description]
    return {row[0]: dict(zip(columns, row)) for row in rows}

