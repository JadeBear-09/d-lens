from typing import Literal

from pydantic import BaseModel, Field

FailureType = Literal[
    "retrieval_failure",
    "hallucination_risk",
    "invalid_json",
    "tool_call_failure",
    "latency_spike",
    "token_cost_spike",
    "user_dissatisfaction",
    "unknown",
]

Severity = Literal["P1", "P2", "P3", "P4"]
JudgementSource = Literal["offline_rules", "online_llm_assisted"]


class FailureReport(BaseModel):
    trace_id: str
    failure_type: FailureType
    severity: Severity
    root_cause: str
    evidence: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    judgement_source: JudgementSource = "offline_rules"


class SimilarReport(FailureReport):
    similarity_score: float = Field(ge=0.0, le=1.0)


class TraceQueuedResponse(BaseModel):
    trace_id: str
    status: Literal["queued"]
