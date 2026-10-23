"""Smoke test: the database is up, the schema is applied, and vector search works.

Needs the local database (./scripts/db-up.sh). Skipped when DATABASE_URL is not set,
for example in CI.
"""

import os

import numpy as np
import pytest
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set; local database not configured"
)

EXPECTED_TABLES = {
    "documents",
    "chunks",
    "summaries",
    "generated_queries",
    "embeddings",
    "eval_queries",
    "schema_version",
}


@pytest.fixture
def conn():
    from rse.common.db import connect

    with connect() as c:
        yield c


def test_schema_v0_applied(conn) -> None:
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    ).fetchall()
    assert EXPECTED_TABLES <= {r[0] for r in rows}
    version = conn.execute("SELECT version FROM schema_version WHERE version = 'v0'").fetchone()
    assert version is not None


def test_insert_and_query_vector(conn) -> None:
    with conn.transaction(force_rollback=True):
        conn.execute(
            "INSERT INTO documents (doc_id, title, category, source_type, content) "
            "VALUES ('smoke-doc', 'Smoke test', 'test', 'synthetic', 'smoke')"
        )
        texts = [
            "How to reset your password",
            "Connecting to the office VPN",
            "Password expiry and changing your password",
        ]
        vectors = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.9, 0.1, 0.0]]
        chunk_ids = []
        for i, (text, vec) in enumerate(zip(texts, vectors, strict=True)):
            chunk_id = conn.execute(
                "INSERT INTO chunks (doc_id, chunk_set, chunk_index, content) "
                "VALUES ('smoke-doc', 'smoke', %s, %s) RETURNING chunk_id",
                (i, text),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO embeddings (target_type, target_id, model, dim, embedding) "
                "VALUES ('chunk', %s, 'smoke-3d', 3, %s)",
                (chunk_id, np.array(vec)),
            )
            chunk_ids.append(chunk_id)

        nearest = conn.execute(
            "SELECT target_id FROM embeddings WHERE model = 'smoke-3d' "
            "ORDER BY embedding <=> %s LIMIT 2",
            (np.array([1.0, 0.0, 0.0]),),
        ).fetchall()
        assert [r[0] for r in nearest] == [chunk_ids[0], chunk_ids[2]]

        keyword = conn.execute(
            "SELECT chunk_id FROM chunks WHERE chunk_set = 'smoke' "
            "AND tsv @@ plainto_tsquery('english', 'password') ORDER BY chunk_index"
        ).fetchall()
        assert [r[0] for r in keyword] == [chunk_ids[0], chunk_ids[2]]

    leftover = conn.execute("SELECT count(*) FROM documents WHERE doc_id = 'smoke-doc'").fetchone()
    assert leftover[0] == 0
