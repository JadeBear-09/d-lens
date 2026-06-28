from app.core.config import get_settings
from app.schemas.report import FailureType
from app.schemas.trace import TraceIn

FAILED_TOOL_STATUSES = {"failed", "error", "timeout", "exception"}
NEGATIVE_FEEDBACK = {"thumbs_down", "negative", "bad", "1_star", "one_star"}


def has_failed_tool(trace: TraceIn) -> bool:
    return any(tool.status.lower() in FAILED_TOOL_STATUSES for tool in trace.tool_calls)


def has_negative_feedback(trace: TraceIn) -> bool:
    if trace.user_feedback is None:
        return False
    return trace.user_feedback.lower() in NEGATIVE_FEEDBACK


def total_tokens(trace: TraceIn) -> int:
    return trace.input_tokens + trace.output_tokens


def top_retrieval_score(trace: TraceIn) -> float | None:
    if not trace.retrieved_chunks:
        return None
    return trace.retrieved_chunks[0].score


def has_retrieval_failure(trace: TraceIn) -> bool:
    settings = get_settings()
    score = top_retrieval_score(trace)
    return score is not None and score < settings.retrieval_score_threshold


def has_hallucination_risk(trace: TraceIn) -> bool:
    if not trace.llm_answer.strip():
        return False

    answer = trace.llm_answer.lower()
    context = " ".join(chunk.text for chunk in trace.retrieved_chunks).lower()
    if not context.strip():
        return True

    answer_terms = {term for term in answer.split() if len(term) > 4}
    context_terms = set(context.split())
    if not answer_terms:
        return False

    overlap_ratio = len(answer_terms & context_terms) / len(answer_terms)
    return overlap_ratio < 0.15


def classify_failure(trace: TraceIn) -> FailureType:
    settings = get_settings()

    if not trace.json_valid:
        return "invalid_json"

    if has_failed_tool(trace):
        return "tool_call_failure"

    if has_retrieval_failure(trace):
        return "retrieval_failure"

    if has_hallucination_risk(trace):
        return "hallucination_risk"

    if trace.latency_ms > settings.latency_spike_ms:
        return "latency_spike"

    if total_tokens(trace) > settings.token_cost_spike:
        return "token_cost_spike"

    if has_negative_feedback(trace):
        return "user_dissatisfaction"

    return "unknown"
