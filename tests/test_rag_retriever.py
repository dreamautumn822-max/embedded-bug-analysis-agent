from pathlib import Path

import pytest
from langchain_core.documents import Document

from app.rag.config import RAGSettings
from app.rag.ranking import RankedDocument
from app.rag.reranker import RerankerError, rerank_candidates as real_rerank_candidates
from app.rag.retriever import (
    retrieve_related_bugs,
    retrieve_related_code,
    retrieve_related_documents,
)


def _settings(tmp_path: Path, *, rerank_provider: str = "local") -> RAGSettings:
    return RAGSettings(
        docs_dir=tmp_path / "docs",
        persist_dir=tmp_path / "chroma",
        embedding_provider="local",
        embedding_model="local-hashing-v1",
        embedding_base_url=None,
        embedding_api_key=None,
        embedding_dimensions=256,
        top_k=2,
        score_threshold=0.1,
        retrieval_mode="hybrid",
        candidate_k=4,
        rerank_provider=rerank_provider,
        bug_history_path=tmp_path / "missing-bugs.json",
        codebase_dir=tmp_path / "missing-code",
    )


def _ranked_document() -> RankedDocument:
    return RankedDocument(
        document=Document(
            page_content="DHCP server 必须等待 bridge ready。",
            metadata={
                "source": "dhcp.md",
                "section": "启动依赖与时序",
                "section_path": "DHCP > 启动依赖与时序",
                "parent_id": "dhcp.md::startup",
                "chunk_id": "dhcp.md::startup::000",
            },
        ),
        score=5.0,
        rank=1,
    )


def test_hybrid_retrieval_keeps_bm25_when_vector_path_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.rag.retriever._vector_search",
        lambda query, settings, source_type: (_ for _ in ()).throw(RuntimeError("vector down")),
    )
    monkeypatch.setattr("app.rag.retriever.load_knowledge_chunks", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.rag.retriever.bm25_search",
        lambda query, documents, k: [_ranked_document()],
    )

    results = retrieve_related_documents(
        "DHCP bridge ready",
        settings=_settings(tmp_path),
    )

    assert results[0]["retrieval_method"] == "bm25_rerank"
    assert results[0]["vector_rank"] is None
    assert results[0]["bm25_rank"] == 1
    assert results[0]["retrieval_warnings"] == ["vector_retrieval_failed"]


def test_cross_encoder_failure_falls_back_to_local_reranker(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.rag.retriever._vector_search",
        lambda query, settings, source_type: [_ranked_document()],
    )
    monkeypatch.setattr("app.rag.retriever.load_knowledge_chunks", lambda *a, **k: [])
    monkeypatch.setattr("app.rag.retriever.bm25_search", lambda *a, **k: [])

    def rerank_with_failure(
        query,
        candidates,
        *,
        provider,
        model_name,
        rerank_weight,
        **kwargs,
    ):
        if provider == "cross_encoder":
            raise RerankerError("model unavailable")
        return real_rerank_candidates(
            query,
            candidates,
            provider=provider,
            model_name=model_name,
            rerank_weight=rerank_weight,
            **kwargs,
        )

    monkeypatch.setattr("app.rag.retriever.rerank_candidates", rerank_with_failure)

    results = retrieve_related_documents(
        "DHCP bridge ready",
        settings=_settings(tmp_path, rerank_provider="cross_encoder"),
    )

    assert results[0]["retrieval_method"] == "vector_rerank"
    assert results[0]["rerank_method"] == "local_feature_fallback"
    assert "model_reranker_failed" in results[0]["retrieval_warnings"]


def test_hybrid_retrieval_raises_when_all_paths_fail(monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        raise RuntimeError("retrieval down")

    monkeypatch.setattr("app.rag.retriever._vector_search", fail)
    monkeypatch.setattr("app.rag.retriever.load_knowledge_chunks", fail)

    with pytest.raises(RuntimeError, match="All configured retrieval paths failed"):
        retrieve_related_documents("query", settings=_settings(tmp_path))


def test_bug_and_code_use_shared_hybrid_retrieval(tmp_path):
    base = _settings(tmp_path)
    settings = RAGSettings(
        **{
            **base.__dict__,
            "docs_dir": Path("data/docs").resolve(),
            "bug_history_path": Path("data/bugs/bug_history.json").resolve(),
            "codebase_dir": Path("data/codebase").resolve(),
            "score_threshold": 0.0,
            "top_k": 3,
        }
    )

    bugs = retrieve_related_bugs(
        "DHCP lease allocation failed bridge upgrade",
        settings=settings,
    )
    code = retrieve_related_code(
        "netifd bridge reload restart DHCP server",
        settings=settings,
    )

    assert bugs[0]["bug_id"] == "BUG-018"
    assert bugs[0]["source_type"] == "bug"
    assert bugs[0]["retrieval_method"] == "hybrid_rrf_rerank"
    assert bugs[0]["vector_rank"] is not None
    assert bugs[0]["bm25_rank"] is not None
    assert code[0]["file"] == "netifd_reload.c"
    assert code[0]["source_type"] == "code"
    assert code[0]["line"] >= 1
    assert "restart_dhcp_server" in code[0]["snippet"]
