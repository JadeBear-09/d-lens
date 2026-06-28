from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
database_url = settings.sqlalchemy_database_url
connect_args = {"check_same_thread": False} if settings.uses_sqlite else {}

engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_report_schema()


def ensure_report_schema() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("reports"):
        return

    column_names = {column["name"] for column in inspector.get_columns("reports")}
    if "judgement_source" in column_names:
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE reports "
                "ADD COLUMN judgement_source VARCHAR(32) "
                "NOT NULL DEFAULT 'offline_rules'"
            )
        )
