import math
from pathlib import Path

from app.rag.config import RAGSettings
from app.rag.retriever import (
    clear_vector_store_cache,
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
    assert documents[0]["retrieval_method"] == "chroma_vector"
    assert documents[0]["score"] >= settings.score_threshold
    assert "地址池" in documents[0]["content"]
    assert retriever_documents[0].metadata["source"] == "dhcp.md"


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
