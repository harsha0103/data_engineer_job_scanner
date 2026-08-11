"""Lookups for embedd.sources — seeded by sql/schema.sql (indeed/dice/ziprecruiter)."""

from .connection import get_connection


def get_source_id(name: str) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM embedd.sources WHERE name = %s", (name,))
            row = cur.fetchone()
    if row is None:
        raise ValueError(f"Unknown source: {name!r} (not seeded in embedd.sources)")
    return row[0]
