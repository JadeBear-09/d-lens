from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.session import Base

json_type = JSON().with_variant(JSONB, "postgresql")


class TraceRecord(Base):
    __tablename__ = "traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    request_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    app_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(json_type, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    report: Mapped["ReportRecord"] = relationship(back_populates="trace", uselist=False)


class ReportRecord(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    trace_request_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("traces.request_id"),
        unique=True,
        index=True,
        nullable=False,
    )
    failure_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list] = mapped_column(json_type, nullable=False)
    suggested_actions: Mapped[list] = mapped_column(json_type, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    judgement_source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="offline_rules",
        server_default="offline_rules",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    trace: Mapped[TraceRecord] = relationship(back_populates="report")
