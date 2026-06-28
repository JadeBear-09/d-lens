#!/usr/bin/env bash
set -u

SERVICE_URL="${SERVICE_URL:-}"
PROJECT_ID="${PROJECT_ID:-}"
API_KEY_SECRET="${API_KEY_SECRET:-dlens-api-key}"
TMP_DIR="$(mktemp -d)"
ANALYZE_ID="req_smoke_analyze_$(date +%s)"
TRACE_ID="req_smoke_trace_$(date +%s)"
AUTH_ARGS=()

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

request() {
  local expected_status="$1"
  local method="$2"
  local url="$3"
  local body_file="${4:-}"
  local response_file="$TMP_DIR/response.json"
  local status

  if [[ -n "$body_file" ]]; then
    status="$(
      curl -sS -o "$response_file" -w "%{http_code}" \
        -X "$method" "$url" \
        "${AUTH_ARGS[@]}" \
        -H "Content-Type: application/json" \
        -d @"$body_file"
    )"
  else
    status="$(curl -sS -o "$response_file" -w "%{http_code}" -X "$method" "${AUTH_ARGS[@]}" "$url")"
  fi

  echo "$method $url -> HTTP $status"
  if [[ "$status" != "$expected_status" ]]; then
    echo "Response body:"
    cat "$response_file"
    echo
    fail "expected HTTP $expected_status, got HTTP $status"
  fi

  cat "$response_file"
  echo
}

contains() {
  local file="$1"
  local needle="$2"
  grep -Fq "$needle" "$file" || {
    echo "Response body:"
    cat "$file"
    echo
    fail "missing expected text: $needle"
  }
}

echo "D-Lens Cloud Run smoke test"
if [[ -z "$SERVICE_URL" ]]; then
  fail "SERVICE_URL must be set, for example https://YOUR_CLOUD_RUN_URL"
fi
echo "SERVICE_URL=$SERVICE_URL"

if [[ -z "${DLENS_API_KEY:-}" && -n "$PROJECT_ID" ]] && command -v gcloud >/dev/null 2>&1; then
  DLENS_API_KEY="$(
    gcloud secrets versions access latest \
      --project="$PROJECT_ID" \
      --secret="$API_KEY_SECRET" 2>/dev/null || true
  )"
fi

if [[ -z "${DLENS_API_KEY:-}" ]]; then
  fail "DLENS_API_KEY is not set and Secret Manager secret $API_KEY_SECRET was not readable"
fi

AUTH_ARGS=(-H "X-API-Key: $DLENS_API_KEY")
echo "API key: configured"
echo

HEALTH_FILE="$TMP_DIR/health.json"
curl -sS -o "$HEALTH_FILE" -w "GET $SERVICE_URL/health -> HTTP %{http_code}\n" "$SERVICE_URL/health" \
  | tee "$TMP_DIR/health.status"
contains "$TMP_DIR/health.status" "HTTP 200"
contains "$HEALTH_FILE" '"status":"ok"'
contains "$HEALTH_FILE" '"judgement_source":"offline_rules"'
cat "$HEALTH_FILE"
echo
echo

DOCS_FILE="$TMP_DIR/docs.html"
DOCS_STATUS="$(curl -sS -o "$DOCS_FILE" -w "%{http_code}" "$SERVICE_URL/docs")"
echo "GET $SERVICE_URL/docs -> HTTP $DOCS_STATUS"
[[ "$DOCS_STATUS" == "200" ]] || fail "expected /docs HTTP 200, got HTTP $DOCS_STATUS"
echo

request "200" "GET" "$SERVICE_URL/api/v1/reports?limit=5" > "$TMP_DIR/list.out"
cat "$TMP_DIR/list.out"
echo

ANALYZE_PAYLOAD="$TMP_DIR/analyze.json"
cat > "$ANALYZE_PAYLOAD" <<JSON
{
  "request_id": "$ANALYZE_ID",
  "app_name": "d-lens-cloudrun-smoke",
  "user_query": "Why was my payment declined?",
  "retrieved_chunks": [
    {
      "chunk_id": "doc_smoke_001",
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
  "timestamp": "2026-06-25T10:30:00Z"
}
JSON

ANALYZE_OUT="$TMP_DIR/analyze.out"
request "200" "POST" "$SERVICE_URL/api/v1/analyze" "$ANALYZE_PAYLOAD" | tee "$ANALYZE_OUT"
contains "$ANALYZE_OUT" "\"trace_id\":\"$ANALYZE_ID\""
contains "$ANALYZE_OUT" '"judgement_source":"offline_rules"'
echo

ANALYZE_GET_OUT="$TMP_DIR/analyze_get.out"
request "200" "GET" "$SERVICE_URL/api/v1/reports/$ANALYZE_ID" | tee "$ANALYZE_GET_OUT"
contains "$ANALYZE_GET_OUT" "\"trace_id\":\"$ANALYZE_ID\""
contains "$ANALYZE_GET_OUT" '"failure_type":"invalid_json"'
echo

TRACE_PAYLOAD="$TMP_DIR/trace.json"
cat > "$TRACE_PAYLOAD" <<JSON
{
  "request_id": "$TRACE_ID",
  "app_name": "d-lens-cloudrun-smoke",
  "user_query": "Why did document search answer with unrelated refund info?",
  "retrieved_chunks": [
    {
      "chunk_id": "doc_smoke_002",
      "text": "Refunds are processed within 5-7 days.",
      "score": 0.32
    }
  ],
  "llm_answer": "Your refund will arrive in 5-7 days.",
  "tool_calls": [],
  "latency_ms": 1800,
  "input_tokens": 700,
  "output_tokens": 220,
  "json_valid": true,
  "user_feedback": "thumbs_down",
  "timestamp": "2026-06-25T10:45:00Z"
}
JSON

TRACE_OUT="$TMP_DIR/trace.out"
request "202" "POST" "$SERVICE_URL/api/v1/traces" "$TRACE_PAYLOAD" | tee "$TRACE_OUT"
contains "$TRACE_OUT" "\"trace_id\":\"$TRACE_ID\""
echo

TRACE_GET_OUT="$TMP_DIR/trace_get.out"
for attempt in 1 2 3 4 5; do
  if request "200" "GET" "$SERVICE_URL/api/v1/reports/$TRACE_ID" > "$TRACE_GET_OUT" 2>/dev/null; then
    cat "$TRACE_GET_OUT"
    contains "$TRACE_GET_OUT" "\"trace_id\":\"$TRACE_ID\""
    contains "$TRACE_GET_OUT" '"judgement_source":"offline_rules"'
    echo
    echo "PASS: Cloud Run smoke test complete"
    exit 0
  fi
  echo "Report not ready yet; retry $attempt/5"
  sleep 2
done

cat "$TRACE_GET_OUT" 2>/dev/null || true
fail "trace report did not become readable"
