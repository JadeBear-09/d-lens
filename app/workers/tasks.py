from app.db.repository import get_trace, save_report
from app.db.session import SessionLocal, init_db
from app.schemas.trace import TraceIn
from app.services.analyzer import Analyzer
from app.workers.celery_app import celery_app


@celery_app.task(
    name="app.workers.tasks.analyze_trace_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def analyze_trace_task(trace_id: str) -> dict:
    init_db()
    db = SessionLocal()
    try:
        trace_record = get_trace(db, trace_id)
        if trace_record is None:
            return {"trace_id": trace_id, "status": "missing_trace"}

        trace = TraceIn.model_validate(trace_record.raw_payload)
        report = Analyzer().analyze(trace)
        save_report(db, report)
        return report.model_dump(mode="json")
    finally:
        db.close()
