from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RetrievedChunk(BaseModel):
    chunk_id: str | None = None
    text: str = ""
    score: float = Field(default=0.0, ge=0.0, le=1.0)


class ToolCall(BaseModel):
    tool_name: str
    status: str
    latency_ms: int = Field(default=0, ge=0)
    error: str | None = None


class TraceIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: str = Field(min_length=1)
    app_name: str = "unknown-app"
    user_query: str
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
    llm_answer: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    latency_ms: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    json_valid: bool = True
    user_feedback: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def raw_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
