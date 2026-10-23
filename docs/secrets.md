# How secrets are handled (RSE-16)

## Rules

1. **Secrets live only in `.env`.** It is git-ignored (`.gitignore` blocks `.env` and `.env.*`,
   but keeps `.env.example`). Code reads them from environment variables via `python-dotenv`.
2. **`.env.example` holds names and harmless placeholders only** (`change-me`,
   `replace-with-your-key`). Copy it to `.env` and fill in real values locally.
3. **Never hard-code, print or log a secret.** The Claude wrapper logs tokens, cost and latency,
   never prompt text or keys.
4. **Datasets are public or synthetic.** No real employee, customer or personal data.

## Secrets in this project

| Variable | Used by | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | `rse.common.llm` | Claude Console → API keys (project key, spend limit set) |
| `POSTGRES_PASSWORD` | Docker Compose database | Any local value; generated with `openssl rand -hex 16` |
| `DATABASE_URL` | `rse.common.db` | Same user and password as above, port 5433 |

## Automatic checks

- **pre-commit** runs `gitleaks` and `detect-private-key` on every commit, and blocks it if a
  secret is staged. Install once with `uv run pre-commit install`.
- **CI** runs the same hooks on every pull request (`pre-commit run --all-files`).

## If a secret is committed by mistake

1. Revoke or rotate it immediately (for an API key: delete it in the Claude Console).
2. Remove it from the code and commit the fix.
3. Removing it from Git history is not enough once it has been pushed: the rotation in step 1
   is what makes it safe.
