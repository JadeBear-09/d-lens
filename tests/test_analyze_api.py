import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app
from app.schemas.status import build_service_status


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "dlens_status": "offline",
        "mode": "local_rules_only",
        "api_key_status": "not_used",
        "api_key_owner": "none",
        "external_llm_calls": False,
        "judgement_source": "offline_rules",
    }


def test_status_shows_online_without_leaking_key() -> None:
    response = build_service_status(Settings(openai_api_key="dummy-openai-key"))

    assert response.dlens_status == "online"
    assert response.mode == "user_llm_key_active"
    assert response.api_key_status == "user_provided"
    assert response.api_key_owner == "user"
    assert response.external_llm_calls is True
    assert "dummy-openai-key" not in response.model_dump_json()


def test_cloud_sql_socket_builds_sqlalchemy_url() -> None:
    settings = Settings(
        instance_unix_socket="/cloudsql/project:asia-south1:dlens-postgres",
        db_user="dlens",
        db_pass="example-pass:with@chars",
        db_name="dlens",
    )

    database_url = settings.sqlalchemy_database_url

    assert database_url.drivername == "postgresql+psycopg"
    assert database_url.username == "dlens"
    assert database_url.password == "example-pass:with@chars"
    assert database_url.database == "dlens"
    assert database_url.query["host"] == "/cloudsql/project:asia-south1:dlens-postgres"


def test_cloud_sql_socket_requires_database_fields() -> None:
    settings = Settings(instance_unix_socket="/cloudsql/project:asia-south1:dlens-postgres")

    with pytest.raises(ValueError, match="DB_USER, DB_PASS, DB_NAME"):
        _ = settings.sqlalchemy_database_url


def test_api_key_auth_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("DLENS_API_KEY", "test-api-key")
    get_settings.cache_clear()

    try:
        with TestClient(app) as client:
            health = client.get("/health")
            unauthenticated = client.get("/api/v1/reports")
            authenticated = client.get(
                "/api/v1/reports",
                headers={"X-API-Key": "test-api-key"},
            )
            metrics = client.get("/metrics")

        assert health.status_code == 200
        assert unauthenticated.status_code == 401
        assert unauthenticated.json()["detail"] == "Invalid or missing API key"
        assert authenticated.status_code == 200
        assert metrics.status_code == 401
    finally:
        get_settings.cache_clear()


def test_analyze_returns_and_persists_report() -> None:
    payload = {
        "request_id": "req_api_001",
        "app_name": "customer-support-rag",
        "user_query": "Why was my payment declined?",
        "retrieved_chunks": [
            {
                "chunk_id": "doc_1",
                "text": "Refunds are processed within 5-7 days.",
                "score": 0.41,
            }
        ],
        "llm_answer": "Your refund will arrive in 5-7 days.",
        "tool_calls": [
            {
                "tool_name": "payment_status_api",
                "status": "failed",
                "error": "HTTP 503",
            }
        ],
        "latency_ms": 4300,
        "input_tokens": 900,
        "output_tokens": 500,
        "json_valid": False,
        "user_feedback": "thumbs_down",
        "timestamp": "2026-06-23T10:30:00Z",
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 200
        report = response.json()
        assert report["trace_id"] == "req_api_001"
        assert report["failure_type"] == "invalid_json"
        assert report["severity"] == "P2"
        assert "json_valid was false" in report["evidence"]
        assert report["judgement_source"] == "offline_rules"

        persisted = client.get("/api/v1/reports/req_api_001")
        assert persisted.status_code == 200
        assert persisted.json()["trace_id"] == "req_api_001"
        assert persisted.json()["judgement_source"] == "offline_rules"
