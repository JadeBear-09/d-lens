from app.schemas.trace import TraceIn
from app.services.classifier import classify_failure


def base_trace(**overrides) -> TraceIn:
    payload = {
        "request_id": "req_test",
        "app_name": "test-app",
        "user_query": "How do I fix payment decline?",
        "retrieved_chunks": [{"chunk_id": "doc_1", "text": "Payment decline docs", "score": 0.9}],
        "llm_answer": "Check payment decline status.",
        "tool_calls": [],
        "latency_ms": 1000,
        "input_tokens": 100,
        "output_tokens": 100,
        "json_valid": True,
        "user_feedback": None,
    }
    payload.update(overrides)
    return TraceIn.model_validate(payload)


def test_invalid_json_has_first_priority() -> None:
    trace = base_trace(
        json_valid=False,
        tool_calls=[{"tool_name": "payment_api", "status": "failed", "error": "HTTP 503"}],
    )

    assert classify_failure(trace) == "invalid_json"


def test_tool_call_failure() -> None:
    trace = base_trace(
        tool_calls=[{"tool_name": "payment_api", "status": "failed", "error": "HTTP 503"}]
    )

    assert classify_failure(trace) == "tool_call_failure"


def test_retrieval_failure_uses_top_chunk_score() -> None:
    trace = base_trace(
        retrieved_chunks=[{"chunk_id": "doc_1", "text": "Refund docs", "score": 0.41}]
    )

    assert classify_failure(trace) == "retrieval_failure"


def test_latency_and_token_failures() -> None:
    assert classify_failure(base_trace(latency_ms=6000)) == "latency_spike"
    assert classify_failure(base_trace(input_tokens=2500, output_tokens=1000)) == "token_cost_spike"


def test_user_dissatisfaction_and_unknown() -> None:
    assert classify_failure(base_trace(user_feedback="thumbs_down")) == "user_dissatisfaction"
    assert classify_failure(base_trace()) == "unknown"
