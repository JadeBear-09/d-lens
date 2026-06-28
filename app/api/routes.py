import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.metrics import TRACES_INGESTED
from app.core.security import require_api_key
from app.db.repository import get_report, list_reports, save_report, save_trace
from app.db.session import get_db
from app.schemas.report import FailureReport, SimilarReport, TraceQueuedResponse
from app.schemas.trace import TraceIn
from app.services.analyzer import Analyzer
from app.workers.tasks import analyze_trace_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])
_analyzer: Analyzer | None = None
DbSession = Annotated[Session, Depends(get_db)]
ReportLimit = Annotated[int, Query(ge=1, le=100)]
SimilarLimit = Annotated[int, Query(ge=1, le=20)]


def get_analyzer() -> Analyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = Analyzer()
    return _analyzer


AnalyzerDependency = Annotated[Analyzer, Depends(get_analyzer)]


@router.post(
    "/traces",
    response_model=TraceQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["traces"],
)
def ingest_trace(trace: TraceIn, db: DbSession) -> TraceQueuedResponse:
    save_trace(db, trace)
    TRACES_INGESTED.inc()

    try:
        analyze_trace_task.delay(trace.request_id)
    except Exception as exc:  # pragma: no cover - broker availability varies
        logger.warning("Celery unavailable; processing trace inline: %s", exc)
        report = get_analyzer().analyze(trace)
        save_report(db, report)

    return TraceQueuedResponse(trace_id=trace.request_id, status="queued")


@router.post("/analyze", response_model=FailureReport, tags=["analysis"])
def analyze_now(
    trace: TraceIn,
    db: DbSession,
    analyzer: AnalyzerDependency,
) -> FailureReport:
    save_trace(db, trace)
    TRACES_INGESTED.inc()
    report = analyzer.analyze(trace)
    save_report(db, report)
    return report


@router.get("/reports", response_model=list[FailureReport], tags=["reports"])
def list_recent_reports(
    db: DbSession,
    limit: ReportLimit = 20,
) -> list[FailureReport]:
    return list_reports(db, limit=limit)


@router.get("/reports/{trace_id}", response_model=FailureReport, tags=["reports"])
def get_rca_report(trace_id: str, db: DbSession) -> FailureReport:
    report = get_report(db, trace_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/reports/{trace_id}/similar", response_model=list[SimilarReport], tags=["reports"])
def get_similar_reports(
    trace_id: str,
    db: DbSession,
    analyzer: AnalyzerDependency,
    limit: SimilarLimit = 5,
) -> list[SimilarReport]:
    report = get_report(db, trace_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return analyzer.vector_store.search_similar(report, limit=limit)
