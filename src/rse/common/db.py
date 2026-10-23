"""PostgreSQL connection helpers for the RSE database."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector


def database_url() -> str:
    """Return DATABASE_URL from the environment or the local .env file."""
    load_dotenv()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")
    return url


@contextmanager
def connect(url: str | None = None) -> Iterator[psycopg.Connection]:
    """Open a connection with pgvector types registered.

    Commits on normal exit and rolls back if an exception is raised.
    """
    with psycopg.connect(url or database_url()) as conn:
        register_vector(conn)
        yield conn
