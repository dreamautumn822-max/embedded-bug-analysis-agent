from pathlib import Path

from app.rag.config import RAGSettings
from scripts.evaluate_retrieval import run_retrieval_evaluation


def _settings(tmp_path: Path) -> RAGSettings:
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
    )


def test_retrieval_evaluation_reports_pipeline_and_latency(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "scripts.evaluate_retrieval.retrieve_related_documents",
        lambda query, settings: [
            {
                "chunk_id": "doc-a",
                "retrieval_method": "hybrid_rrf_rerank",
                "rerank_method": "local_feature",
            },
            {
                "chunk_id": "other",
                "retrieval_method": "hybrid_rrf_rerank",
                "rerank_method": "local_feature",
            },
        ],
    )

    report = run_retrieval_evaluation(
        [
            {
                "case_id": "CASE-1",
                "query": "query",
                "relevant_chunk_ids": ["doc-a"],
            }
        ],
        settings=_settings(tmp_path),
        top_k=2,
    )

    assert report["retrieval_mode"] == "hybrid"
    assert report["rerank_provider"] == "local"
    assert report["metrics"]["recall_at_k"] == 1.0
    assert report["average_latency_ms"] >= 0
    assert report["p95_latency_ms"] >= 0
    assert report["cases"][0]["retrieval_methods"] == ["hybrid_rrf_rerank"]
