import math
from pathlib import Path

from app.rag.config import RAGSettings
from app.rag.retriever import (
    clear_vector_store_cache,
    content_snippet,
    create_doc_retriever,
    retrieve_related_documents,
)
from app.rag.vector_store import (
    LocalHashEmbeddings,
    build_vector_store,
    sync_vector_store,
)


def _settings(docs_dir: Path, persist_dir: Path) -> RAGSettings:
    return RAGSettings(
        docs_dir=docs_dir,
        persist_dir=persist_dir,
        embedding_provider="local",
        embedding_model="local-hashing-v1",
        embedding_base_url=None,
        embedding_api_key=None,
        embedding_dimensions=256,
        top_k=3,
        score_threshold=0.05,
        retrieval_mode="vector",
        candidate_k=3,
        rerank_provider="none",
        bug_history_path=docs_dir.parent / "missing-bugs.json",
        codebase_dir=docs_dir.parent / "missing-code",
    )


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return numerator / (left_norm * right_norm)


def test_local_hash_embeddings_are_deterministic_and_lexically_relevant():
    embeddings = LocalHashEmbeddings(dimensions=256)

    first = embeddings.embed_query("DHCP lease allocation failed")
    repeated = embeddings.embed_query("DHCP lease allocation failed")
    related = embeddings.embed_query("DHCP address lease failure")
    unrelated = embeddings.embed_query("WiFi signal channel interference")

    assert first == repeated
    assert _cosine(first, related) > _cosine(first, unrelated)


def test_build_embeddings_uses_fastembed_provider(monkeypatch, tmp_path: Path):
    captured = {}

    class FakeFastEmbedEmbeddings:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        "app.rag.vector_store.FastEmbedLocalEmbeddings",
        FakeFastEmbedEmbeddings,
    )
    settings = RAGSettings(
        **{
            **_settings(tmp_path / "docs", tmp_path / "chroma").__dict__,
            "embedding_provider": "fastembed",
            "embedding_model": "BAAI/bge-small-zh-v1.5",
            "embedding_cache_dir": tmp_path / "models",
            "embedding_max_length": 384,
            "embedding_threads": 2,
        }
    )

    from app.rag.vector_store import build_embeddings

    embedding = build_embeddings(settings)

    assert isinstance(embedding, FakeFastEmbedEmbeddings)
    assert captured == {
        "model_name": "BAAI/bge-small-zh-v1.5",
        "max_length": 384,
        "cache_dir": tmp_path / "models",
        "threads": 2,
    }


def test_content_snippet_skips_markdown_headings():
    content = "# DHCP 模块说明  \n## 启动依赖与时序  \nDHCP server 必须等待 bridge ready。\n\n下一段"

    assert content_snippet(content) == "DHCP server 必须等待 bridge ready。"


def test_chroma_vector_retrieval_returns_relevant_document(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "dhcp.md").write_text(
        "# DHCP 模块说明\n\nDHCP 地址池负责分配租约，网桥未就绪会导致分配失败。",
        encoding="utf-8",
    )
    (docs_dir / "wifi.md").write_text(
        "# WiFi 模块说明\n\n无线模块负责信道选择和射频功率管理。",
        encoding="utf-8",
    )
    settings = _settings(docs_dir, tmp_path / "chroma")

    clear_vector_store_cache()
    try:
        documents = retrieve_related_documents(
            "DHCP lease allocation failed 网桥未就绪",
            settings=settings,
        )
        retriever_documents = create_doc_retriever(settings).invoke(
            "DHCP lease allocation failed 网桥未就绪"
        )
    finally:
        clear_vector_store_cache()

    assert documents
    assert documents[0]["source"] == "dhcp.md"
    assert documents[0]["retrieval_method"] == "vector"
    assert documents[0]["score"] >= settings.score_threshold
    assert documents[0]["chunk_id"].startswith("dhcp.md::")
    assert documents[0]["evidence_id"].startswith("doc:dhcp.md::")
    assert documents[0]["section"] == "DHCP 模块说明"
    assert documents[0]["vector_rank"] == 1
    assert documents[0]["bm25_rank"] is None
    assert documents[0]["snippet"].startswith("DHCP 地址池负责")
    assert "地址池" in documents[0]["content"]
    assert retriever_documents[0].metadata["source"] == "dhcp.md"
    assert retriever_documents[0].metadata["retrieval_method"] == "vector"


def test_hybrid_retrieval_exposes_fusion_and_rerank_metadata(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "pppoe.md").write_text(
        "# PPPoE\n\n## Link flap 与重试定时器\n\n"
        "WAN link flap 恢复后必须重新启动 retry timer。",
        encoding="utf-8",
    )
    (docs_dir / "wifi.md").write_text(
        "# Wi-Fi\n\n## 自动信道\n\n无线客户端在换信道时保持连接。",
        encoding="utf-8",
    )
    settings = RAGSettings(
        **{
            **_settings(docs_dir, tmp_path / "chroma").__dict__,
            "retrieval_mode": "hybrid",
            "candidate_k": 4,
            "rerank_provider": "local",
        }
    )

    clear_vector_store_cache()
    try:
        documents = retrieve_related_documents(
            "PPPoE link flap retry timer stopped",
            settings=settings,
        )
    finally:
        clear_vector_store_cache()

    assert documents[0]["section"] == "Link flap 与重试定时器"
    assert documents[0]["retrieval_method"] == "hybrid_rrf_rerank"
    assert documents[0]["rerank_method"] == "local_feature"
    assert documents[0]["vector_rank"] is not None
    assert documents[0]["bm25_rank"] is not None
    assert documents[0]["fusion_score"] > 0
    assert 0 <= documents[0]["rerank_score"] <= 1


def test_vector_store_sync_adds_updates_and_deletes_documents(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    dhcp_path = docs_dir / "dhcp.md"
    wifi_path = docs_dir / "wifi.md"
    dhcp_path.write_text("# DHCP\n\n旧版地址池说明。", encoding="utf-8")
    wifi_path.write_text("# WiFi\n\n无线信道说明。", encoding="utf-8")
    settings = _settings(docs_dir, tmp_path / "chroma")

    store = build_vector_store(settings=settings)
    assert store._collection.count() == 2
    assert sync_vector_store(store, docs_dir) == {
        "added": 0,
        "deleted": 0,
        "total": 2,
    }

    dhcp_path.write_text("# DHCP\n\n新版地址池迁移说明。", encoding="utf-8")
    wifi_path.unlink()

    assert sync_vector_store(store, docs_dir) == {
        "added": 1,
        "deleted": 2,
        "total": 1,
    }
    records = store.get(include=["documents", "metadatas"])
    assert len(records["ids"]) == 1
    assert records["metadatas"][0]["source"] == "dhcp.md"
    assert "新版地址池" in records["documents"][0]
