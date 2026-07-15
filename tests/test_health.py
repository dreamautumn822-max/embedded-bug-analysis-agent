from fastapi.testclient import TestClient

from app.main import app


def test_health_details_exposes_runtime_pipeline_without_secrets(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "hybrid")
    monkeypatch.setenv("RAG_RERANK_PROVIDER", "local")

    response = TestClient(app).get("/health/details")

    assert response.status_code == 200
    payload = response.json()
    assert {
        key: payload[key]
        for key in (
            "status",
            "embedding_provider",
            "embedding_model",
            "retrieval_mode",
            "rerank_provider",
        )
    } == {
        "status": "ok",
        "embedding_provider": "local",
        "embedding_model": "local-hashing-v1",
        "retrieval_mode": "hybrid",
        "rerank_provider": "local",
    }
    assert payload["git_history_enabled"] is False
    assert payload["authentication_enabled"] is False
    assert payload["queue"]["status"] in {"ok", "unavailable"}
    assert "api_key" not in payload
