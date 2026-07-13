from functools import lru_cache
from threading import RLock

from langchain_chroma import Chroma
from langchain_core.vectorstores import VectorStoreRetriever

from app.rag.config import RAGSettings
from app.rag.vector_store import build_vector_store, sync_vector_store


_INDEX_LOCK = RLock()


def create_doc_retriever(settings: RAGSettings | None = None) -> VectorStoreRetriever:
    settings = settings or RAGSettings.from_env()
    store = _get_synced_store(settings)
    return store.as_retriever(search_kwargs={"k": settings.top_k})


def retrieve_related_documents(
    query: str,
    settings: RAGSettings | None = None,
) -> list[dict]:
    settings = settings or RAGSettings.from_env()
    store = _get_synced_store(settings)
    matches = store.similarity_search_with_relevance_scores(query, k=settings.top_k)

    return [
        {
            "source": document.metadata.get("source", "unknown"),
            "score": round(max(0.0, min(1.0, float(score))), 4),
            "snippet": _content_snippet(document.page_content),
            "content": document.page_content.strip(),
            "retrieval_method": "chroma_vector",
        }
        for document, score in matches
        if score >= settings.score_threshold
    ]


def clear_vector_store_cache() -> None:
    _cached_vector_store.cache_clear()


def _get_synced_store(settings: RAGSettings) -> Chroma:
    with _INDEX_LOCK:
        store = _cached_vector_store(settings)
        sync_vector_store(store, settings.docs_dir)
        return store


@lru_cache(maxsize=8)
def _cached_vector_store(settings: RAGSettings) -> Chroma:
    return build_vector_store(settings=settings)


def _content_snippet(content: str, limit: int = 420) -> str:
    paragraphs = [
        " ".join(line.strip() for line in paragraph.splitlines() if line.strip())
        for paragraph in content.split("\n\n")
        if paragraph.strip() and not paragraph.lstrip().startswith("#")
    ]
    snippet = paragraphs[0] if paragraphs else content.strip().splitlines()[0]
    if len(snippet) <= limit:
        return snippet
    return snippet[: limit - 3].rstrip() + "..."
