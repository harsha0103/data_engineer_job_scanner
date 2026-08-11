"""Storage for embedd.base_resume — single row, your one source-of-truth resume."""

from uuid import UUID

from .connection import get_connection


def set_base_resume(file_path: str, resume_text: str, embedding: list[float]) -> UUID:
    """Replaces the base resume. There's only ever one — a fresh resume replaces
    the old row rather than accumulating history (that's what git/your own
    file versions are for, not this table)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM embedd.base_resume")
            cur.execute(
                """
                INSERT INTO embedd.base_resume (file_path, resume_text, embedding)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (file_path, resume_text, embedding),
            )
            resume_id = cur.fetchone()[0]
    return resume_id


def get_base_resume() -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, file_path, resume_text, embedding, updated_at FROM embedd.base_resume LIMIT 1"
            )
            row = cur.fetchone()
            if row is None:
                return None
            columns = [d.name for d in cur.description]
    return dict(zip(columns, row))
