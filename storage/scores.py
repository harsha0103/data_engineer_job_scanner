"""Storage for embedd.job_scores — one row per job (UNIQUE(job_id)); re-score = update."""

from uuid import UUID

from .connection import get_connection


def upsert_score(
    job_id: UUID,
    *,
    overall_score: float,
    skills_match: float,
    level_match: float,
    location_match: float,
    comp_match: float,
    notes: str,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO embedd.job_scores (
                    job_id, overall_score, skills_match, level_match, location_match, comp_match, notes
                )
                VALUES (%(job_id)s, %(overall_score)s, %(skills_match)s, %(level_match)s,
                        %(location_match)s, %(comp_match)s, %(notes)s)
                ON CONFLICT (job_id) DO UPDATE SET
                    overall_score = EXCLUDED.overall_score,
                    skills_match = EXCLUDED.skills_match,
                    level_match = EXCLUDED.level_match,
                    location_match = EXCLUDED.location_match,
                    comp_match = EXCLUDED.comp_match,
                    notes = EXCLUDED.notes,
                    scored_at = now()
                """,
                {
                    "job_id": job_id,
                    "overall_score": overall_score,
                    "skills_match": skills_match,
                    "level_match": level_match,
                    "location_match": location_match,
                    "comp_match": comp_match,
                    "notes": notes,
                },
            )


def get_score(job_id: UUID) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT overall_score, skills_match, level_match, location_match, comp_match, notes, scored_at
                FROM embedd.job_scores WHERE job_id = %s
                """,
                (job_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            columns = [d.name for d in cur.description]
    return dict(zip(columns, row))
