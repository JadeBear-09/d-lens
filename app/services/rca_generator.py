import json
import logging

from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.metrics import LLM_JSON_FAILURES
from app.schemas.report import FailureReport, FailureType, Severity
from app.schemas.trace import TraceIn
from app.services.classifier import (
    has_failed_tool,
    has_negative_feedback,
    has_retrieval_failure,
    top_retrieval_score,
    total_tokens,
)

logger = logging.getLogger(__name__)


class RCAGenerator:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def generate(
        self,
        trace: TraceIn,
        failure_type: FailureType,
        severity: Severity,
    ) -> FailureReport:
        evidence = build_evidence(trace)
        suggested_actions = build_actions(trace, failure_type)

        if self.settings.llm_online:
            report = self._generate_with_openai(
                trace,
                failure_type,
                severity,
                evidence,
                suggested_actions,
            )
            if report is not None:
                return report

        return self._generate_deterministic(
            trace,
            failure_type,
            severity,
            evidence,
            suggested_actions,
        )

    def _generate_deterministic(
        self,
        trace: TraceIn,
        failure_type: FailureType,
        severity: Severity,
        evidence: list[str],
        suggested_actions: list[str],
    ) -> FailureReport:
        root_cause = deterministic_root_cause(trace, failure_type)
        confidence = confidence_score(failure_type, evidence)
        return FailureReport(
            trace_id=trace.request_id,
            failure_type=failure_type,
            severity=severity,
            root_cause=root_cause,
            evidence=evidence,
            suggested_actions=suggested_actions,
            confidence=confidence,
            judgement_source="offline_rules",
        )

    def _generate_with_openai(
        self,
        trace: TraceIn,
        failure_type: FailureType,
        severity: Severity,
        evidence: list[str],
        suggested_actions: list[str],
    ) -> FailureReport | None:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.settings.openai_api_key)
            response = client.chat.completions.create(
                model=self.settings.openai_chat_model,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Generate concise JSON for an RCA report. Use only supplied evidence. "
                            "Fields: trace_id, failure_type, severity, root_cause, evidence, "
                            "suggested_actions, confidence."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "trace": trace.raw_payload(),
                                "failure_type": failure_type,
                                "severity": severity,
                                "evidence": evidence,
                                "suggested_actions": suggested_actions,
                            }
                        ),
                    },
                ],
                temperature=0.1,
            )
            content = response.choices[0].message.content or "{}"
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise ValueError("OpenAI RCA response was not a JSON object")
            payload.update(
                {
                    "trace_id": trace.request_id,
                    "failure_type": failure_type,
                    "severity": severity,
                    "evidence": evidence,
                    "suggested_actions": suggested_actions,
                    "judgement_source": "online_llm_assisted",
                }
            )
            return FailureReport.model_validate(payload)
        except (
            ImportError,
            ValidationError,
            KeyError,
            IndexError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            LLM_JSON_FAILURES.inc()
            logger.warning("OpenAI RCA generation failed, using deterministic fallback: %s", exc)
            return None
        except Exception as exc:  # pragma: no cover - network/provider failures vary
            LLM_JSON_FAILURES.inc()
            logger.warning("OpenAI RCA generation failed, using deterministic fallback: %s", exc)
            return None


def build_evidence(trace: TraceIn) -> list[str]:
    evidence: list[str] = []
    settings = get_settings()

    if not trace.json_valid:
        evidence.append("json_valid was false")

    score = top_retrieval_score(trace)
    if score is not None and score < settings.retrieval_score_threshold:
        evidence.append(
            f"Top retrieved chunk score was {score:.2f}, below threshold "
            f"{settings.retrieval_score_threshold:.2f}"
        )
    elif not trace.retrieved_chunks:
        evidence.append("No retrieved context was provided")

    for tool in trace.tool_calls:
        if tool.status.lower() in {"failed", "error", "timeout", "exception"}:
            detail = f"{tool.tool_name} status was {tool.status}"
            if tool.error:
                detail += f" with error {tool.error}"
            evidence.append(detail)

    if trace.latency_ms > settings.latency_spike_ms:
        evidence.append(f"Latency was {trace.latency_ms}ms, above spike threshold")
    elif trace.latency_ms > settings.minor_latency_ms:
        evidence.append(f"Latency was {trace.latency_ms}ms, above warning threshold")

    if total_tokens(trace) > settings.token_cost_spike:
        evidence.append(f"Token usage was {total_tokens(trace)} tokens, above cost threshold")

    if has_negative_feedback(trace):
        evidence.append(f"User feedback was {trace.user_feedback}")

    return evidence or ["No strong failure signal was detected"]


def build_actions(trace: TraceIn, failure_type: FailureType) -> list[str]:
    actions_by_type: dict[FailureType, list[str]] = {
        "invalid_json": [
            "Validate JSON response before returning to the client",
            "Use schema-constrained model output or a repair step",
        ],
        "tool_call_failure": [
            "Add retry, timeout, and fallback handling for failed tools",
            "Alert on repeated tool/API failures by tool name",
        ],
        "retrieval_failure": [
            "Add hybrid BM25 + vector retrieval",
            "Improve reranking and minimum-score thresholds",
        ],
        "hallucination_risk": [
            "Require answer grounding against retrieved context",
            "Return an uncertainty response when context is missing",
        ],
        "latency_spike": [
            "Add latency budgets around retrieval, tools, and model calls",
            "Cache repeated retrieval/model work where safe",
        ],
        "token_cost_spike": [
            "Trim prompts and retrieved chunks before model calls",
            "Track token budgets by app and route",
        ],
        "user_dissatisfaction": [
            "Review failed conversation examples with user feedback",
            "Add targeted evaluation cases for this query pattern",
        ],
        "unknown": [
            "Add richer trace fields for prompts, model responses, and tool outputs",
            "Review raw logs for missing failure signals",
        ],
    }

    actions = actions_by_type[failure_type].copy()

    if has_failed_tool(trace) and failure_type != "tool_call_failure":
        actions.append("Add retry and fallback behavior for failed tool calls")
    if has_retrieval_failure(trace) and failure_type != "retrieval_failure":
        actions.append("Improve retrieval reranking for low-score context")
    if not trace.json_valid and failure_type != "invalid_json":
        actions.append("Validate JSON response before returning to the client")

    return actions


def deterministic_root_cause(trace: TraceIn, failure_type: FailureType) -> str:
    if failure_type == "invalid_json":
        return (
            "The model response failed JSON validation. The trace also shows related reliability "
            "signals that should be checked before the response is sent downstream."
        )
    if failure_type == "tool_call_failure":
        return (
            "A required tool or API call failed, so the model likely answered without reliable "
            "external system state."
        )
    if failure_type == "retrieval_failure":
        return (
            "The top retrieved context was below the safe relevance threshold, so the answer may "
            "have been generated from weak or mismatched context."
        )
    if failure_type == "hallucination_risk":
        return (
            "The answer appears weakly grounded in retrieved context, which raises hallucination "
            "risk for this request."
        )
    if failure_type == "latency_spike":
        return (
            "The request exceeded the latency spike threshold and needs component-level timing "
            "review."
        )
    if failure_type == "token_cost_spike":
        return "The request used more tokens than the configured cost threshold."
    if failure_type == "user_dissatisfaction":
        return (
            "The user gave negative feedback even though no stronger deterministic signal was "
            "found."
        )
    return "No primary failure signal was detected from the available trace fields."


def confidence_score(failure_type: FailureType, evidence: list[str]) -> float:
    if failure_type == "unknown":
        return 0.35
    score = 0.58 + min(len(evidence), 5) * 0.05
    if failure_type in {"invalid_json", "tool_call_failure", "retrieval_failure"}:
        score += 0.08
    return round(min(score, 0.95), 2)
