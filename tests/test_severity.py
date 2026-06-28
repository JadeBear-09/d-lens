from app.schemas.trace import TraceIn
from app.services.severity import score_severity


def trace(**overrides) -> TraceIn:
    payload = {
        "request_id": "req_sev",
        "app_name": "test-app",
        "user_query": "Question",
        "retrieved_chunks": [{"text": "Helpful context", "score": 0.9}],
        "llm_answer": "Answer from helpful context",
        "tool_calls": [],
        "latency_ms": 1000,
        "input_tokens": 100,
        "output_tokens": 100,
        "json_valid": True,
    }
    payload.update(overrides)
    return TraceIn.model_validate(payload)


def test_p1_requires_tool_failure_negative_feedback_and_high_latency() -> None:
    item = trace(
        tool_calls=[{"tool_name": "payment_api", "status": "failed"}],
        user_feedback="thumbs_down",
        latency_ms=6000,
    )

    assert score_severity(item) == "P1"


def test_p2_for_invalid_json_retrieval_or_tool_failure() -> None:
    assert score_severity(trace(json_valid=False)) == "P2"
    assert score_severity(trace(retrieved_chunks=[{"text": "Weak context", "score": 0.2}])) == "P2"
    assert score_severity(trace(tool_calls=[{"tool_name": "api", "status": "failed"}])) == "P2"


def test_p3_for_minor_latency_token_cost_or_hallucination_risk() -> None:
    assert score_severity(trace(latency_ms=3500)) == "P3"
    assert score_severity(trace(input_tokens=2500, output_tokens=1000)) == "P3"
    assert score_severity(trace(), failure_type="hallucination_risk") == "P3"


def test_p4_for_low_risk_unknown() -> None:
    assert score_severity(trace()) == "P4"
