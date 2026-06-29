# D-Lens

<p align="center">
  <a href="https://github.com/JadeBear-09/d-lens/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/JadeBear-09/d-lens?style=social"></a>
  <a href="https://github.com/JadeBear-09/d-lens/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/JadeBear-09/d-lens/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Last commit" src="https://img.shields.io/github/last-commit/JadeBear-09/d-lens">
  <img alt="Issues" src="https://img.shields.io/github/issues/JadeBear-09/d-lens">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white">
  <img alt="Postgres" src="https://img.shields.io/badge/Postgres-ready-4169E1?logo=postgresql&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-compose-2496ED?logo=docker&logoColor=white">
</p>

<p align="center">
  <a href="https://dlens-api-wuscfbl3cq-el.a.run.app/docs">Live API docs</a>
  · <a href="#quick-start">Quick start</a>
  · <a href="#api-surface">API</a>
  · <a href="#failure-taxonomy">Failure taxonomy</a>
  · <a href="docs/COMMIT_GUIDE.md">Commit guide</a>
</p>

D-Lens is a reliability and root-cause analysis microservice for LLM applications. Send
one chatbot, RAG, or agent trace to D-Lens and get a structured diagnosis: failure type,
severity, evidence, likely root cause, and suggested actions.

It works offline by default with deterministic rules. When `OPENAI_API_KEY` is set, it
can use an LLM to improve report wording while rule-based failure type, severity,
evidence, and actions remain the source of truth.

## What It Solves

| Signal | What D-Lens checks |
| --- | --- |
| Retrieval quality | Low-score context, missing citations, weak evidence |
| Output validity | Invalid JSON and schema-hostile responses |
| Tool reliability | Failed API/tool calls and surfaced errors |
| Performance | Latency spikes and token-cost spikes |
| Feedback | Negative user feedback and repeat incidents |
| Operations | Stored RCA reports, similar-incident lookup, Prometheus metrics |

## Architecture

```text
LLM app trace
  -> FastAPI ingestion endpoint
  -> deterministic reliability checks
  -> severity scoring
  -> RCA report builder
  -> optional LLM wording pass
  -> Postgres report store
  -> Qdrant similar-report search
  -> Prometheus metrics
```

Local Docker Compose starts FastAPI, Celery, Postgres, Redis, and Qdrant. Non-Docker
development can fall back to SQLite at `./dlens.db`.

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

Open:

```text
API docs: http://localhost:8000/docs
Health:   http://localhost:8000/health
Status:   http://localhost:8000/status
Metrics:  http://localhost:8000/metrics
```

In local `ENV=dev`, protected routes work without `DLENS_API_KEY`. In non-dev
environments, set `DLENS_API_KEY` and send it as `X-API-Key`.

## Example Trace

```json
{
  "request_id": "req_001",
  "app_name": "customer-support-rag",
  "user_query": "Why was my payment declined?",
  "retrieved_chunks": [
    {
      "chunk_id": "doc_1",
      "text": "Refunds are processed within 5-7 days.",
      "score": 0.41
    }
  ],
  "llm_answer": "Your refund will arrive in 5-7 days.",
  "tool_calls": [
    {
      "tool_name": "payment_status_api",
      "status": "failed",
      "latency_ms": 1200,
      "error": "HTTP 503"
    }
  ],
  "latency_ms": 4300,
  "input_tokens": 900,
  "output_tokens": 500,
  "json_valid": false,
  "user_feedback": "thumbs_down",
  "timestamp": "2026-06-23T10:30:00Z"
}
```

Analyze immediately:

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d @sample_payloads/bad_rag_trace.json
```

With API key enabled:

```bash
curl -X POST "$DLENS_URL/api/v1/analyze" \
  -H "X-API-Key: $DLENS_API_KEY" \
  -H "Content-Type: application/json" \
  -d @sample_payloads/bad_rag_trace.json
```

## Output Report

```json
{
  "trace_id": "req_001",
  "failure_type": "invalid_json",
  "severity": "P2",
  "root_cause": "The model response failed JSON validation. The trace also shows related reliability signals that should be checked before the response is sent downstream.",
  "evidence": [
    "json_valid was false",
    "Top retrieved chunk score was 0.41, below threshold 0.60",
    "payment_status_api status was failed with error HTTP 503",
    "User feedback was thumbs_down"
  ],
  "suggested_actions": [
    "Validate JSON response before returning to the client",
    "Use schema-constrained model output or a repair step",
    "Improve retrieval reranking for low-score context"
  ],
  "confidence": 0.95,
  "judgement_source": "offline_rules"
}
```

## Failure Taxonomy

| Failure type | Typical trigger |
| --- | --- |
| `retrieval_failure` | Retrieved context score is too low |
| `hallucination_risk` | Answer does not look grounded in retrieved evidence |
| `invalid_json` | `json_valid=false` or downstream schema failure |
| `tool_call_failure` | Tool/API call reports failed status or error |
| `latency_spike` | Request crosses configured latency threshold |
| `token_cost_spike` | Token usage crosses configured cost threshold |
| `user_dissatisfaction` | User feedback is negative |
| `unknown` | Trace lacks enough failure evidence |

Severity:

- `P1`: failed tool + negative feedback + latency over spike threshold
- `P2`: invalid JSON, low retrieval score, or failed tool
- `P3`: latency/token warning, hallucination risk, or negative feedback
- `P4`: low-risk or unknown signal

## API Surface

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service health |
| `GET` | `/status` | Mode, dependency, and config status |
| `POST` | `/api/v1/analyze` | Analyze one trace immediately |
| `POST` | `/api/v1/traces` | Store trace and queue/background analysis |
| `GET` | `/api/v1/reports?limit=20` | List recent reports |
| `GET` | `/api/v1/reports/{trace_id}` | Fetch one report |
| `GET` | `/api/v1/reports/{trace_id}/similar?limit=5` | Find similar reports |
| `GET` | `/metrics` | Prometheus metrics |

## Configuration

| Variable | Purpose |
| --- | --- |
| `ENV` | `dev`, `test`, or production environment name |
| `DLENS_API_KEY` | Enables `X-API-Key` auth for protected routes |
| `DATABASE_URL` | SQLAlchemy database URL |
| `REDIS_URL` | Celery broker URL |
| `QDRANT_URL` | Qdrant URL for similar-report search |
| `RETRIEVAL_SCORE_THRESHOLD` | Low retrieval score threshold, default `0.60` |
| `LATENCY_SPIKE_MS` | Spike threshold, default `5000` |
| `MINOR_LATENCY_MS` | Warning threshold, default `3000` |
| `TOKEN_COST_SPIKE` | Token warning threshold, default `3000` |
| `OPENAI_API_KEY` | Optional LLM-assisted RCA wording and OpenAI embeddings |

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest -q
```

## Project Map

```text
app/api/       FastAPI routes
app/core/      config, security, metrics, logging
app/db/        SQLAlchemy models and repository layer
app/schemas/   Pydantic trace, report, and status contracts
app/services/  classifier, severity, RCA, embeddings, vector search
app/workers/   Celery app and background tasks
tests/         pytest suite
sample_payloads/ example traces for smoke testing
```

## Data Safety

D-Lens stores traces and reports. Do not send secrets, full private prompts, payment
data, health data, or user data that should not be persisted. For production use, add
tenant isolation, retention policies, redaction, encryption, and access review.

## Roadmap

- Add richer evaluation fixtures for multi-signal incidents
- Add OpenTelemetry trace IDs and dashboards
- Add configurable failure policies per app/team
- Add report export for incident review workflows
- Add more embedding/vector backends for similar-incident search

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/COMMIT_GUIDE.md](docs/COMMIT_GUIDE.md).
