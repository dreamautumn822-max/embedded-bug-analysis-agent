from pathlib import Path

import pytest

from app.rag.config import RAGSettings


RAG_ENV_NAMES = (
    "CHROMA_DIR",
    "DOCS_DIR",
    "EMBEDDING_PROVIDER",
    "EMBEDDING_MODEL",
    "EMBEDDING_BASE_URL",
    "EMBEDDING_API_KEY",
    "EMBEDDING_DIMENSIONS",
    "RAG_TOP_K",
    "RAG_SCORE_THRESHOLD",
)


def test_rag_settings_default_to_offline_local_embeddings(monkeypatch):
    for name in RAG_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)

    settings = RAGSettings.from_env()

    assert settings.embedding_provider == "local"
    assert settings.embedding_model == "local-hashing-v1"
    assert settings.embedding_dimensions == 1024
    assert settings.top_k == 3
    assert settings.score_threshold == 0.1
    assert settings.docs_dir == Path("data/docs").resolve()
    assert settings.persist_dir == Path(".chroma").resolve()


def test_rag_settings_read_openai_compatible_embedding_config(monkeypatch, tmp_path):
    monkeypatch.setenv("DOCS_DIR", str(tmp_path / "docs"))
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("EMBEDDING_MODEL", "custom-embedding")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://embedding.example.com/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("RAG_TOP_K", "5")
    monkeypatch.setenv("RAG_SCORE_THRESHOLD", "0.25")

    settings = RAGSettings.from_env()

    assert settings.embedding_provider == "openai"
    assert settings.embedding_model == "custom-embedding"
    assert settings.embedding_base_url == "https://embedding.example.com/v1"
    assert settings.embedding_api_key == "test-key"
    assert settings.top_k == 5
    assert settings.score_threshold == 0.25


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("EMBEDDING_PROVIDER", "unsupported"),
        ("EMBEDDING_DIMENSIONS", "32"),
        ("RAG_TOP_K", "0"),
        ("RAG_SCORE_THRESHOLD", "1.1"),
    ],
)
def test_rag_settings_reject_invalid_values(monkeypatch, name, value):
    for env_name in RAG_ENV_NAMES:
        monkeypatch.delenv(env_name, raising=False)
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError):
        RAGSettings.from_env()
