from prometheus_client import Counter, Histogram

TRACES_INGESTED = Counter(
    "dlens_traces_ingested_total",
    "Total LLM traces ingested.",
)

REPORTS_GENERATED = Counter(
    "dlens_reports_generated_total",
    "Total RCA reports generated.",
)

FAILURE_TYPE_COUNT = Counter(
    "dlens_failure_type_total",
    "Total RCA reports by primary failure type.",
    ["failure_type"],
)

HTTP_REQUEST_LATENCY = Histogram(
    "dlens_http_request_latency_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"],
)

TRACE_LATENCY_MS = Histogram(
    "dlens_trace_latency_ms",
    "Application trace latency in milliseconds.",
    buckets=(100, 500, 1000, 2000, 3000, 5000, 10000, 30000),
)

LLM_JSON_FAILURES = Counter(
    "dlens_llm_json_failures_total",
    "Total invalid JSON or LLM structured-output parse failures.",
)
