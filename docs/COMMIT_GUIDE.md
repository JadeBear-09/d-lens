# Commit Guide

Use Conventional Commits for clean history and readable changelogs.

## Format

```text
type(scope): short summary
```

Use imperative mood:

```text
feat(api): store queued trace reports
fix(severity): classify failed tools as P2
docs(readme): add failure taxonomy
test(classifier): cover invalid json traces
ci: run ruff and pytest on pull requests
```

## Types

| Type | Use when |
| --- | --- |
| `feat` | adding behavior |
| `fix` | correcting behavior |
| `docs` | changing docs |
| `test` | adding or changing tests |
| `refactor` | moving code without behavior change |
| `perf` | improving latency or resource use |
| `build` | changing Docker, packaging, or dependencies |
| `ci` | changing GitHub Actions |
| `chore` | maintenance |

## Suggested Scopes

- `api`
- `classifier`
- `severity`
- `rca`
- `db`
- `vector-search`
- `worker`
- `metrics`
- `docs`
- `ci`

## Hygiene

- Keep save-point commits out of PR history.
- Mention migration or data-store impact in the body when relevant.
- Include validation commands in PR description.
- Never commit secrets, private traces, production logs, or raw customer data.
