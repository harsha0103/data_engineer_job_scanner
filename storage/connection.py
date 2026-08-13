"""Postgres connection for the embedd schema.

Pooled, not one-connection-per-call. That used to be the right call when
Postgres ran on localhost (connection setup was sub-millisecond) — but now
that the database is remote (Supabase, for the scheduled cloud routine to
reach), each fresh connection costs a real TLS handshake round-trip, measured
at ~1.7s. A page that opens dozens of connections in a loop (e.g. one
get_resume_for_job() call per job) turned unusable once the DB moved off
localhost — a 30s Streamlit test timeout was the symptom. Pooling reuses
already-open connections instead of paying that cost every call.
"""

import os
from contextlib import contextmanager

from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

load_dotenv()

_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            os.environ["DATABASE_URL"],
            min_size=1,
            max_size=5,
            configure=register_vector,  # run once per physical connection the pool opens
        )
    return _pool


@contextmanager
def get_connection():
    """Yields a pooled psycopg connection; commits on clean exit, rolls back on
    error, then returns the connection to the pool (doesn't close it)."""
    with _get_pool().connection() as conn:
        yield conn
