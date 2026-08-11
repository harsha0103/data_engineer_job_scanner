"""Storage for embedd.scan_runs — one row per sweep of one source, for observability."""

from uuid import UUID

from .connection import get_connection


def start_run(source_id: int) -> UUID:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO embedd.scan_runs (source_id, status) VALUES (%s, 'running') RETURNING id",
                (source_id,),
            )
            run_id = cur.fetchone()[0]
    return run_id


def finish_run(run_id: UUID, *, jobs_found: int, jobs_new: int, status: str = "success") -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE embedd.scan_runs
                SET finished_at = now(), jobs_found = %s, jobs_new = %s, status = %s
                WHERE id = %s
                """,
                (jobs_found, jobs_new, status, run_id),
            )
