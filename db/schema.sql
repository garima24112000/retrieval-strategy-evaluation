-- RSE schema v0 (RSE-15)
-- Idempotent: safe to run more than once. Indexes for search arrive in v1 (Day 14, load the database).

SET client_min_messages = warning;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS schema_version (
    version     TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per source document (public or synthetic).
CREATE TABLE IF NOT EXISTS documents (
    doc_id        TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    category      TEXT NOT NULL,
    topic         TEXT,
    source_type   TEXT NOT NULL CHECK (source_type IN ('public', 'synthetic')),
    source_url    TEXT,
    license       TEXT,
    content       TEXT NOT NULL,
    content_hash  TEXT,
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Chunks of a document. chunk_set names the chunking config (e.g. 'heading-512'),
-- so 256 / 512 / 768 variants can live side by side for the ablation.
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id      BIGSERIAL PRIMARY KEY,
    doc_id        TEXT NOT NULL REFERENCES documents (doc_id) ON DELETE CASCADE,
    chunk_set     TEXT NOT NULL,
    chunk_index   INTEGER NOT NULL,
    heading_path  TEXT,
    content       TEXT NOT NULL,
    token_count   INTEGER,
    tsv           TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    UNIQUE (doc_id, chunk_set, chunk_index)
);

-- LLM-written summary per document (summary search).
CREATE TABLE IF NOT EXISTS summaries (
    summary_id      BIGSERIAL PRIMARY KEY,
    doc_id          TEXT NOT NULL REFERENCES documents (doc_id) ON DELETE CASCADE,
    model           TEXT NOT NULL,
    prompt_version  TEXT NOT NULL,
    content         TEXT NOT NULL,
    tsv             TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (doc_id, model, prompt_version)
);

-- LLM-written likely user questions per document (doc2query / reverse keywording).
CREATE TABLE IF NOT EXISTS generated_queries (
    gq_id           BIGSERIAL PRIMARY KEY,
    doc_id          TEXT NOT NULL REFERENCES documents (doc_id) ON DELETE CASCADE,
    model           TEXT NOT NULL,
    prompt_version  TEXT NOT NULL,
    query_text      TEXT NOT NULL,
    tsv             TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', query_text)) STORED,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Embeddings for chunks, summaries and generated queries, one row per (target, model).
-- No fixed dimension, so two embedding models can be compared; per-model HNSW
-- indexes are added in v1 with a cast, e.g. ((embedding::vector(384))).
CREATE TABLE IF NOT EXISTS embeddings (
    target_type  TEXT NOT NULL CHECK (target_type IN ('chunk', 'summary', 'generated_query')),
    target_id    BIGINT NOT NULL,
    model        TEXT NOT NULL,
    dim          INTEGER NOT NULL CHECK (dim > 0),
    embedding    VECTOR NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (target_type, target_id, model),
    CHECK (vector_dims(embedding) = dim)
);

-- Evaluation questions with gold documents and reference answers.
CREATE TABLE IF NOT EXISTS eval_queries (
    query_id          TEXT PRIMARY KEY,
    query_text        TEXT NOT NULL,
    query_type        TEXT NOT NULL CHECK (query_type IN (
                          'exact', 'acronym', 'jargon', 'paraphrase', 'vague',
                          'typo', 'multi_part', 'troubleshooting')),
    split             TEXT NOT NULL CHECK (split IN ('train', 'val', 'test')),
    origin            TEXT NOT NULL CHECK (origin IN ('human', 'synthetic')),
    gold_doc_ids      TEXT[] NOT NULL CHECK (cardinality(gold_doc_ids) > 0),
    reference_answer  TEXT,
    group_id          TEXT,
    dataset_version   TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO schema_version (version) VALUES ('v0') ON CONFLICT (version) DO NOTHING;
