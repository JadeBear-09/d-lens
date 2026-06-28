from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session

from app.db.models import ReportRecord, TraceRecord
from app.schemas.report import FailureReport
from app.schemas.trace import TraceIn


def save_trace(db: Session, trace: TraceIn) -> TraceRecord:
    existing = get_trace(db, trace.request_id)
    if existing is not None:
        existing.app_name = trace.app_name
        existing.user_query = trace.user_query
        existing.raw_payload = trace.raw_payload()
        existing.timestamp = trace.timestamp
        db.commit()
        db.refresh(existing)
        return existing

    record = TraceRecord(
        request_id=trace.request_id,
        app_name=trace.app_name,
        user_query=trace.user_query,
        raw_payload=trace.raw_payload(),
        timestamp=trace.timestamp,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_trace(db: Session, request_id: str) -> TraceRecord | None:
    return db.scalar(select(TraceRecord).where(TraceRecord.request_id == request_id))


def save_report(db: Session, report: FailureReport) -> ReportRecord:
    existing = get_report_record(db, report.trace_id)
    if existing is not None:
        existing.failure_type = report.failure_type
        existing.severity = report.severity
        existing.root_cause = report.root_cause
        existing.evidence = report.evidence
        existing.suggested_actions = report.suggested_actions
        existing.confidence = report.confidence
        existing.judgement_source = report.judgement_source
        db.commit()
        db.refresh(existing)
        return existing

    record = ReportRecord(
        trace_request_id=report.trace_id,
        failure_type=report.failure_type,
        severity=report.severity,
        root_cause=report.root_cause,
        evidence=report.evidence,
        suggested_actions=report.suggested_actions,
        confidence=report.confidence,
        judgement_source=report.judgement_source,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_report_record(db: Session, trace_id: str) -> ReportRecord | None:
    return db.scalar(select(ReportRecord).where(ReportRecord.trace_request_id == trace_id))


def get_report(db: Session, trace_id: str) -> FailureReport | None:
    record = get_report_record(db, trace_id)
    if record is None:
        return None
    return record_to_report(record)


def list_reports(db: Session, limit: int = 20) -> list[FailureReport]:
    statement: Select[tuple[ReportRecord]] = (
        select(ReportRecord).order_by(desc(ReportRecord.created_at)).limit(limit)
    )
    return [record_to_report(record) for record in db.scalars(statement)]


def record_to_report(record: ReportRecord) -> FailureReport:
    return FailureReport(
        trace_id=record.trace_request_id,
        failure_type=record.failure_type,
        severity=record.severity,
        root_cause=record.root_cause,
        evidence=record.evidence,
        suggested_actions=record.suggested_actions,
        confidence=record.confidence,
        judgement_source=record.judgement_source,
    )
