from app.core.config import get_settings
from app.schemas.report import FailureType, Severity
from app.schemas.trace import TraceIn
from app.services.classifier import (
    has_failed_tool,
    has_negative_feedback,
    has_retrieval_failure,
    total_tokens,
)


def score_severity(trace: TraceIn, failure_type: FailureType | None = None) -> Severity:
    settings = get_settings()

    if (
        has_failed_tool(trace)
        and has_negative_feedback(trace)
        and trace.latency_ms > settings.latency_spike_ms
    ):
        return "P1"

    if not trace.json_valid or has_retrieval_failure(trace) or has_failed_tool(trace):
        return "P2"

    latency_warning = trace.latency_ms > settings.minor_latency_ms
    token_warning = total_tokens(trace) > settings.token_cost_spike
    if latency_warning or token_warning:
        return "P3"

    if has_negative_feedback(trace) or failure_type == "hallucination_risk":
        return "P3"

    return "P4"
