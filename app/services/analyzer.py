from app.core.metrics import (
    FAILURE_TYPE_COUNT,
    LLM_JSON_FAILURES,
    REPORTS_GENERATED,
    TRACE_LATENCY_MS,
)
from app.schemas.report import FailureReport
from app.schemas.trace import TraceIn
from app.services.classifier import classify_failure
from app.services.rca_generator import RCAGenerator
from app.services.severity import score_severity
from app.services.vector_store import QdrantVectorStore, VectorStore


class Analyzer:
    def __init__(
        self,
        rca_generator: RCAGenerator | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.rca_generator = rca_generator or RCAGenerator()
        self.vector_store = vector_store or QdrantVectorStore()

    def analyze(self, trace: TraceIn) -> FailureReport:
        failure_type = classify_failure(trace)
        severity = score_severity(trace, failure_type)
        report = self.rca_generator.generate(trace, failure_type, severity)

        REPORTS_GENERATED.inc()
        FAILURE_TYPE_COUNT.labels(failure_type=report.failure_type).inc()
        TRACE_LATENCY_MS.observe(trace.latency_ms)
        if not trace.json_valid:
            LLM_JSON_FAILURES.inc()

        self.vector_store.upsert_report(report)
        return report
