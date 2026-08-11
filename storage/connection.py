"""Postgres connection for the embedd schema.

One connection per call, not pooled — this is a personal batch tool run a
few times a day, not a service handling concurrent requests, so a pool would
be solving a problem we don't have.
"""

import os
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector

load_dotenv()


@contextmanager
def get_connection():
    """Yields a psycopg connection; commits on clean exit, rolls back on error."""
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    register_vector(conn)  # lets vector columns round-trip as plain Python lists
    try:
        with conn:
            yield conn
    finally:
        conn.close()
