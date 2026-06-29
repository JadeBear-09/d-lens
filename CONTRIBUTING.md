# Contributing

Keep D-Lens changes focused, testable, and easy to operate locally.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

For full-stack local development:

```bash
cp .env.example .env
docker compose up --build
```

## Validation

```bash
python -m ruff check .
python -m pytest -q
```

Run Docker Compose smoke checks when changes touch database, Redis, Qdrant, Celery, or
container setup.

## Pull Request Expectations

- Keep one PR focused on one reliability behavior, endpoint, or documentation goal.
- Add or update tests for classifier, severity, API, persistence, or search behavior.
- Include sample request/response output for API-facing changes.
- Document new environment variables in `README.md`.
- Do not commit `.env`, API keys, private traces, customer prompts, or production logs.

## Commit Style

Use [docs/COMMIT_GUIDE.md](docs/COMMIT_GUIDE.md).
