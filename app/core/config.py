from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "dev"
    log_level: str = "INFO"
    dlens_api_key: str | None = None

    database_url: str = "sqlite:///./dlens.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_task_always_eager: bool = False

    db_user: str | None = None
    db_pass: str | None = None
    db_name: str | None = None
    instance_unix_socket: str | None = None

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "dlens_reports"

    retrieval_score_threshold: float = 0.60
    latency_spike_ms: int = 5000
    minor_latency_ms: int = 3000
    token_cost_spike: int = 3000

    openai_api_key: str | None = Field(default=None)
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    @property
    def llm_online(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key.strip())

    @property
    def sqlalchemy_database_url(self) -> str | URL:
        if not self.instance_unix_socket:
            return self.database_url

        missing = [
            name
            for name, value in {
                "DB_USER": self.db_user,
                "DB_PASS": self.db_pass,
                "DB_NAME": self.db_name,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(
                "Cloud SQL Unix socket config missing required env vars: "
                + ", ".join(missing)
            )

        return URL.create(
            drivername="postgresql+psycopg",
            username=self.db_user,
            password=self.db_pass,
            database=self.db_name,
            query={"host": self.instance_unix_socket},
        )

    @property
    def uses_sqlite(self) -> bool:
        database_url = self.sqlalchemy_database_url
        return isinstance(database_url, str) and database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
