"""Storage for embedd.applications — one status row per job (UNIQUE(job_id))."""

from uuid import UUID

from .connection import get_connection

VALID_STATUSES = {"not_applied", "draft_ready", "applied", "interviewing", "rejected", "offer"}


def set_status(job_id: UUID, status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Unknown status: {status!r} (expected one of {VALID_STATUSES})")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO embedd.applications (job_id, status, applied_at)
                VALUES (%(job_id)s, %(status)s, CASE WHEN %(status)s = 'applied' THEN now() END)
                ON CONFLICT (job_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    -- keep the original applied_at once set; don't overwrite it
                    -- just because the status changed again later
                    applied_at = COALESCE(embedd.applications.applied_at, EXCLUDED.applied_at),
                    last_updated_at = now()
                """,
                {"job_id": job_id, "status": status},
            )
