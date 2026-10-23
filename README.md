# retrieval-strategy-evaluation

Benchmarking and optimizing retrieval strategies for enterprise IT/HR knowledge-base question answering.

> **Status: scaffolding only.** Nothing below marked *planned* is implemented yet.

## Overview

Retrieval Strategy Evaluation (RSE) is a reproducible benchmark that compares retrieval
strategies for answering questions over an IT/HR knowledge base. The goal is to measure,
under controlled and repeatable conditions, how each strategy trades off retrieval quality,
answer quality, latency, and cost.

Planned dataset:

- ~200 public or synthetic knowledge-base topics (IT support, HR policy, onboarding, etc.)
- 300–400 evaluation questions with labelled relevant documents and reference answers

## Planned retrieval strategies

| Strategy | Family | Status |
| --- | --- | --- |
| BM25 | Lexical | Planned |
| Query expansion | Lexical / query-side | Planned |
| Semantic search (dense embeddings) | Dense | Planned |
| Summary retrieval | Document-side | Planned |
| doc2query | Document-side | Planned |
| Query rewriting / HyDE | Query-side (LLM) | Planned |
| Hybrid with Reciprocal Rank Fusion (RRF) | Hybrid | Planned |
| Cross-encoder reranking | Reranking | Planned |

## Architecture (planned)

```
src/rse/
  config/       experiment and runtime configuration
  data/         corpus and evaluation-set loading/preparation
  retrieval/    retrieval strategies (no answer generation here)
  evaluation/   retrieval and answer-quality metrics
  generation/   LLM answer generation over retrieved context
  api/          HTTP API layer
  common/       shared utilities
configs/        experiment configuration files
experiments/    experiment run outputs (git-ignored)
data/           raw / processed / synthetic datasets (git-ignored)
scripts/        command-line entry points
docker/         container definitions
```

Retrieval and generation are kept separate so retrieval quality can be measured
independently of the LLM used to produce answers.

Planned stack: Python, PostgreSQL + pgvector, open-source embedding and reranker models,
Claude LLMs, FastAPI, Docker.

## Setup

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/) and Docker.

```bash
uv sync --extra dev            # create .venv and install from uv.lock
cp .env.example .env           # fill in local values; never commit .env
uv run pre-commit install      # run lint, format and secret checks on every commit
```

Local database (PostgreSQL + pgvector in Docker, project name `rse`, port 5433):

```bash
./scripts/db-up.sh             # start the database and apply db/schema.sql
docker compose stop            # stop it when you are done; data is kept
```

Claude models are configured by alias in `configs/models.toml`. Check that both answer:

```bash
uv run python scripts/llm_smoke.py
```

Run checks:

```bash
uv run pre-commit run --all-files
uv run pytest
```

Database tests in `tests/integration/` are skipped when `DATABASE_URL` is not set (as in CI).
See [docs/secrets.md](docs/secrets.md) for how secrets are handled.

## Evaluation plan (planned)

Retrieval metrics:

- **Hit@K**: whether any relevant document appears in the top K
- **Recall@K**: fraction of relevant documents retrieved in the top K
- **MRR**: mean reciprocal rank of the first relevant document

End-to-end and operational metrics:

- **Answer accuracy**: generated answers compared against reference answers
- **Latency**: per-query retrieval and generation time
- **Cost**: per-query model/API cost

Every experiment is driven by a versioned config with fixed random seeds, so results can be
reproduced and compared across strategies.

## Development status

- [x] Repository scaffolding, packaging, lint/test tooling, CI
- [x] Local PostgreSQL + pgvector, schema v0, pre-commit with secret scanning, Claude client
- [ ] Dataset curation and synthetic data generation
- [ ] Baseline retrieval (BM25)
- [ ] Dense, hybrid, and reranking strategies
- [ ] Evaluation harness and reporting
- [ ] Answer generation
- [ ] API and Docker deployment
