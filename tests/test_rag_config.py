from pathlib import Path

import pytest

from app.rag.config import RAGSettings


RAG_ENV_NAMES = (
    "CHROMA_DIR",
    "DOCS_DIR",
    "BUG_HISTORY_PATH",
    "CODEBASE_DIR",
    "EMBEDDING_PROVIDER",
    "EMBEDDING_MODEL",
    "EMBEDDING_BASE_URL",
    "EMBEDDING_API_KEY",
    "EMBEDDING_DIMENSIONS",
    "EMBEDDING_CACHE_DIR",
    "EMBEDDING_MAX_LENGTH",
    "EMBEDDING_THREADS",
    "RAG_TOP_K",
    "RAG_SCORE_THRESHOLD",
    "RAG_CHUNK_SIZE",
    "RAG_CHUNK_OVERLAP",
    "RAG_RETRIEVAL_MODE",
    "RAG_CANDIDATE_K",
    "RAG_RRF_K",
    "RAG_VECTOR_WEIGHT",
    "RAG_BM25_WEIGHT",
    "RAG_RERANK_PROVIDER",
    "RAG_RERANK_MODEL",
    "RAG_RERANK_WEIGHT",
    "RAG_RERANK_CACHE_DIR",
    "RAG_RERANK_MAX_LENGTH",
)


def test_rag_settings_default_to_offline_local_embeddings(monkeypatch):
    for name in RAG_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)

    settings = RAGSettings.from_env()

    assert settings.embedding_provider == "local"
    assert settings.embedding_model == "local-hashing-v1"
    assert settings.embedding_dimensions == 1024
    assert settings.embedding_cache_dir == Path(".cache/embeddings").resolve()
    assert settings.embedding_max_length == 512
    assert settings.embedding_threads is None
    assert settings.top_k == 3
    assert settings.score_threshold == 0.1
    assert settings.chunk_size == 300
    assert settings.chunk_overlap == 50
    assert settings.retrieval_mode == "hybrid"
    assert settings.candidate_k == 8
    assert settings.rrf_k == 60
    assert settings.vector_weight == 1.0
    assert settings.bm25_weight == 1.0
    assert settings.rerank_provider == "local"
    assert settings.rerank_model == "ms-marco-MultiBERT-L-12"
    assert settings.rerank_weight == 0.65
    assert settings.rerank_cache_dir == Path(".cache/rerank").resolve()
    assert settings.rerank_max_length == 256
    assert settings.docs_dir == Path("data/docs").resolve()
    assert settings.persist_dir == Path(".chroma").resolve()
    assert settings.bug_history_path == Path("data/bugs/bug_history.json").resolve()
    assert settings.codebase_dir == Path("data/codebase").resolve()


def test_rag_settings_read_openai_compatible_embedding_config(monkeypatch, tmp_path):
    monkeypatch.setenv("DOCS_DIR", str(tmp_path / "docs"))
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("EMBEDDING_MODEL", "custom-embedding")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://embedding.example.com/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("RAG_TOP_K", "5")
    monkeypatch.setenv("RAG_SCORE_THRESHOLD", "0.25")
    monkeypatch.setenv("RAG_CHUNK_SIZE", "480")
    monkeypatch.setenv("RAG_CHUNK_OVERLAP", "60")
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "hybrid")
    monkeypatch.setenv("RAG_CANDIDATE_K", "10")
    monkeypatch.setenv("RAG_RRF_K", "50")
    monkeypatch.setenv("RAG_VECTOR_WEIGHT", "1.2")
    monkeypatch.setenv("RAG_BM25_WEIGHT", "0.8")
    monkeypatch.setenv("RAG_RERANK_PROVIDER", "cross_encoder")
    monkeypatch.setenv("RAG_RERANK_MODEL", "example/reranker")
    monkeypatch.setenv("RAG_RERANK_WEIGHT", "0.75")
    monkeypatch.setenv("RAG_RERANK_CACHE_DIR", str(tmp_path / "rerank"))
    monkeypatch.setenv("RAG_RERANK_MAX_LENGTH", "384")

    settings = RAGSettings.from_env()

    assert settings.embedding_provider == "openai"
    assert settings.embedding_model == "custom-embedding"
    assert settings.embedding_base_url == "https://embedding.example.com/v1"
    assert settings.embedding_api_key == "test-key"
    assert settings.top_k == 5
    assert settings.score_threshold == 0.25
    assert settings.chunk_size == 480
    assert settings.chunk_overlap == 60
    assert settings.candidate_k == 10
    assert settings.rrf_k == 50
    assert settings.vector_weight == 1.2
    assert settings.bm25_weight == 0.8
    assert settings.rerank_provider == "cross_encoder"
    assert settings.rerank_model == "example/reranker"
    assert settings.rerank_weight == 0.75
    assert settings.rerank_cache_dir == (tmp_path / "rerank").resolve()
    assert settings.rerank_max_length == 384


def test_rag_settings_read_fastembed_config(monkeypatch, tmp_path):
    for name in RAG_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fastembed")
    monkeypatch.setenv("EMBEDDING_CACHE_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("EMBEDDING_MAX_LENGTH", "384")
    monkeypatch.setenv("EMBEDDING_THREADS", "2")

    settings = RAGSettings.from_env()

    assert settings.embedding_provider == "fastembed"
    assert settings.embedding_model == "BAAI/bge-small-zh-v1.5"
    assert settings.embedding_cache_dir == (tmp_path / "models").resolve()
    assert settings.embedding_max_length == 384
    assert settings.embedding_threads == 2


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("EMBEDDING_PROVIDER", "unsupported"),
        ("EMBEDDING_DIMENSIONS", "32"),
        ("RAG_TOP_K", "0"),
        ("RAG_SCORE_THRESHOLD", "1.1"),
        ("RAG_CHUNK_SIZE", "0"),
        ("RAG_CHUNK_OVERLAP", "-1"),
        ("RAG_RETRIEVAL_MODE", "invalid"),
        ("RAG_RERANK_PROVIDER", "invalid"),
        ("RAG_RERANK_WEIGHT", "1.1"),
        ("RAG_RRF_K", "0"),
        ("RAG_RERANK_MAX_LENGTH", "0"),
        ("RAG_VECTOR_WEIGHT", "0"),
        ("RAG_BM25_WEIGHT", "0"),
        ("EMBEDDING_MAX_LENGTH", "513"),
        ("EMBEDDING_THREADS", "0"),
    ],
)
def test_rag_settings_reject_invalid_values(monkeypatch, name, value):
    for env_name in RAG_ENV_NAMES:
        monkeypatch.delenv(env_name, raising=False)
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError):
        RAGSettings.from_env()


def test_rag_settings_require_overlap_smaller_than_chunk(monkeypatch):
    for env_name in RAG_ENV_NAMES:
        monkeypatch.delenv(env_name, raising=False)
    monkeypatch.setenv("RAG_CHUNK_SIZE", "50")
    monkeypatch.setenv("RAG_CHUNK_OVERLAP", "50")

    with pytest.raises(ValueError, match="smaller"):
        RAGSettings.from_env()


def test_rag_settings_require_candidate_pool_at_least_top_k(monkeypatch):
    for env_name in RAG_ENV_NAMES:
        monkeypatch.delenv(env_name, raising=False)
    monkeypatch.setenv("RAG_TOP_K", "5")
    monkeypatch.setenv("RAG_CANDIDATE_K", "4")

    with pytest.raises(ValueError, match="CANDIDATE_K"):
        RAGSettings.from_env()
