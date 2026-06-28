# D-Lens

D-Lens is a microservice for diagnosing failures in LLM apps.

Your chatbot, RAG pipeline, or agent sends one request trace to D-Lens. D-Lens stores the trace, classifies the likely failure, scores severity, builds evidence, suggests fixes, and can search for similar past reports.

It works offline by default with deterministic rules. If `OPENAI_API_KEY` is set, it can use an LLM to improve report wording while keeping the rule-based failure type, severity, evidence, and actions as the source of truth.

## What It Is For

- Debugging bad LLM answers
- Checking retrieval quality
- Detecting invalid JSON output
- Detecting failed tool/API calls
- Tracking latency and token-cost spikes
- Saving RCA reports for later lookup
- Finding similar previous failures
- Exposing Prometheus metrics

## Run Locally

```bash
cp .env.example .env
docker compose up --build
```

API docs:

```text
http://localhost:8000/docs
```

Health/status:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/status
```

In local `ENV=dev`, protected routes work without `DLENS_API_KEY`. In non-dev environments, set `DLENS_API_KEY` and send it as `X-API-Key`.

## Main Flow

```text
LLM app trace
  -> POST /api/v1/analyze or /api/v1/traces
  -> D-Lens classifies failure
  -> D-Lens scores severity
  -> D-Lens returns or stores RCA report
  -> reports can be listed, fetched, or searched for similar failures
```

## Input Trace

Send JSON shaped like this:

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

Required fields:

- `request_id`
- `user_query`

Useful optional fields:

- `app_name`
- `retrieved_chunks`
- `llm_answer`
- `tool_calls`
- `latency_ms`
- `input_tokens`
- `output_tokens`
- `json_valid`
- `user_feedback`
- `timestamp`

Extra fields are allowed and stored with the raw trace.

## Output Report

`POST /api/v1/analyze` returns:

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

Failure types:

- `retrieval_failure`
- `hallucination_risk`
- `invalid_json`
- `tool_call_failure`
- `latency_spike`
- `token_cost_spike`
- `user_dissatisfaction`
- `unknown`

Severity:

- `P1`: failed tool + negative feedback + latency over spike threshold
- `P2`: invalid JSON, low retrieval score, or failed tool
- `P3`: latency/token warning, hallucination risk, or negative feedback
- `P4`: low-risk or unknown signal

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service status |
| `GET` | `/status` | Service status and offline/online mode |
| `POST` | `/api/v1/analyze` | Analyze one trace immediately and return report |
| `POST` | `/api/v1/traces` | Store trace and queue/background analysis |
| `GET` | `/api/v1/reports?limit=20` | List recent reports |
| `GET` | `/api/v1/reports/{trace_id}` | Fetch one report |
| `GET` | `/api/v1/reports/{trace_id}/similar?limit=5` | Find similar reports |
| `GET` | `/metrics` | Prometheus metrics |

## Example Calls

Analyze immediately:

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d @sample_payloads/bad_rag_trace.json
```

Queue analysis:

```bash
curl -X POST http://localhost:8000/api/v1/traces \
  -H "Content-Type: application/json" \
  -d @sample_payloads/bad_rag_trace.json
```

Fetch report:

```bash
curl http://localhost:8000/api/v1/reports/req_001
```

With API key enabled:

```bash
curl -X POST "$DLENS_URL/api/v1/analyze" \
  -H "X-API-Key: $DLENS_API_KEY" \
  -H "Content-Type: application/json" \
  -d @sample_payloads/bad_rag_trace.json
```

## Configuration

Important environment variables:

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
| `OPENAI_API_KEY` | Optional; enables LLM-assisted RCA wording and OpenAI embeddings |

## Data Stores

Local Docker Compose starts:

- FastAPI app
- Celery worker
- Postgres
- Redis
- Qdrant

Default non-Docker config falls back to SQLite at `./dlens.db`.

## Notes

- `/api/v1/*` and `/metrics` use `X-API-Key` when `DLENS_API_KEY` is configured.
- `/health`, `/status`, and `/docs` stay open.
- D-Lens stores traces and reports; do not send secrets, full private prompts, or user data that should not be persisted.
