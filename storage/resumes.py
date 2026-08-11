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
