from functools import lru_cache
import logging
import json
import re
from threading import RLock
from time import perf_counter

from langchain_chroma import Chroma
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict

from app.rag.config import RAGSettings
from app.rag.corpus import SUPPORTED_SOURCE_TYPES, load_knowledge_chunks
from app.rag.ranking import (
    FusedCandidate,
    RankedDocument,
    bm25_search,
    reciprocal_rank_fusion,
)
from app.rag.reranker import RerankerError, rerank_candidates
from app.rag.vector_store import build_vector_store, sync_vector_store
from app.observability.metrics import observe_retrieval
from app.observability.tracing import start_span


_INDEX_LOCK = RLock()
_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+")
logger = logging.getLogger(__name__)


class HybridDocumentRetriever(BaseRetriever):
    settings: RAGSettings

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        results = retrieve_related_documents(query, settings=self.settings)
        return [
            Document(
                page_content=result["content"],
                metadata={
                    key: value
                    for key, value in result.items()
                    if key not in {"content", "snippet"} and value is not None
                },
            )
            for result in results
        ]


def create_doc_retriever(settings: RAGSettings | None = None) -> BaseRetriever:
    return HybridDocumentRetriever(settings=settings or RAGSettings.from_env())


def retrieve_related_documents(
    query: str,
    settings: RAGSettings | None = None,
) -> list[dict]:
    return retrieve_knowledge_source(query, source_type="doc", settings=settings)


def retrieve_related_bugs(
    query: str,
    settings: RAGSettings | None = None,
) -> list[dict]:
    return retrieve_knowledge_source(query, source_type="bug", settings=settings)


def retrieve_related_code(
    query: str,
    settings: RAGSettings | None = None,
) -> list[dict]:
    return retrieve_knowledge_source(query, source_type="code", settings=settings)


def retrieve_knowledge_source(
    query: str,
    *,
    source_type: str,
    settings: RAGSettings | None = None,
) -> list[dict]:
    settings = settings or RAGSettings.from_env()
    if source_type not in SUPPORTED_SOURCE_TYPES:
        raise ValueError(f"Unsupported source type: {source_type}")
    with start_span(
        "rag.retrieve",
        {
            "rag.source_type": source_type,
            "rag.retrieval_mode": settings.retrieval_mode,
        },
    ) as span:
        started_at = perf_counter()
        try:
            results = _retrieve_knowledge_source(
                query,
                source_type=source_type,
                settings=settings,
            )
        except Exception:
            span.set_attribute("rag.status", "error")
            observe_retrieval(
                source_type=source_type,
                status="error",
                duration_seconds=perf_counter() - started_at,
            )
            raise

        has_warnings = any(result.get("retrieval_warnings") for result in results)
        status = "degraded" if has_warnings else ("success" if results else "empty")
        span.set_attribute("rag.status", status)
        span.set_attribute("rag.result_count", len(results))
        observe_retrieval(
            source_type=source_type,
            status=status,
            duration_seconds=perf_counter() - started_at,
            results=results,
        )
        return results


def _retrieve_knowledge_source(
    query: str,
    *,
    source_type: str,
    settings: RAGSettings,
) -> list[dict]:
    vector_results: list[RankedDocument] = []
    bm25_results: list[RankedDocument] = []
    errors: list[Exception] = []
    retrieval_warnings: list[str] = []

    if settings.retrieval_mode in {"vector", "hybrid"}:
        try:
            vector_results = _vector_search(query, settings, source_type)
        except Exception as exc:
            errors.append(exc)
            retrieval_warnings.append("vector_retrieval_failed")
            logger.warning("Vector retrieval failed: %s", exc)

    if settings.retrieval_mode in {"bm25", "hybrid"}:
        try:
            bm25_results = bm25_search(
                query,
                load_knowledge_chunks(
                    docs_dir=settings.docs_dir,
                    bug_history_path=settings.bug_history_path,
                    codebase_dir=settings.codebase_dir,
                    chunk_size=settings.chunk_size,
                    chunk_overlap=settings.chunk_overlap,
                    source_types={source_type},
                    git_history_enabled=settings.git_history_enabled,
                    git_max_commits=settings.git_max_commits,
                    git_diff_max_chars=settings.git_diff_max_chars,
                ),
                k=settings.candidate_k,
            )
        except Exception as exc:
            errors.append(exc)
            retrieval_warnings.append("bm25_retrieval_failed")
            logger.warning("BM25 retrieval failed: %s", exc)

    candidates = reciprocal_rank_fusion(
        vector_results,
        bm25_results,
        rrf_k=settings.rrf_k,
        vector_weight=settings.vector_weight,
        bm25_weight=settings.bm25_weight,
    )
    if not candidates:
        if errors:
            raise RuntimeError("All configured retrieval paths failed") from errors[0]
        return []

    try:
        reranked, rerank_method = rerank_candidates(
            query,
            candidates,
            provider=settings.rerank_provider,
            model_name=settings.rerank_model,
            rerank_weight=settings.rerank_weight,
            cache_dir=settings.rerank_cache_dir,
            max_length=settings.rerank_max_length,
        )
    except RerankerError as exc:
        logger.warning("Model reranker failed; using local reranker: %s", exc)
        reranked, _ = rerank_candidates(
            query,
            candidates,
            provider="local",
            model_name=settings.rerank_model,
            rerank_weight=settings.rerank_weight,
            cache_dir=settings.rerank_cache_dir,
            max_length=settings.rerank_max_length,
        )
        rerank_method = "local_feature_fallback"
        retrieval_warnings.append("model_reranker_failed")

    retrieval_method = _retrieval_method(
        vector_results,
        bm25_results,
        rerank_method,
    )
    return [
        _serialize_candidate(
            candidate,
            query=query,
            source_type=source_type,
            rank=rank,
            retrieval_method=retrieval_method,
            rerank_method=rerank_method,
            retrieval_warnings=retrieval_warnings,
        )
        for rank, candidate in enumerate(reranked[: settings.top_k], start=1)
    ]


def clear_vector_store_cache() -> None:
    _cached_vector_store.cache_clear()


def _get_synced_store(settings: RAGSettings) -> Chroma:
    with _INDEX_LOCK:
        store = _cached_vector_store(settings)
        sync_vector_store(
            store,
            settings.docs_dir,
            bug_history_path=settings.bug_history_path,
            codebase_dir=settings.codebase_dir,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            git_history_enabled=settings.git_history_enabled,
            git_max_commits=settings.git_max_commits,
            git_diff_max_chars=settings.git_diff_max_chars,
        )
        return store


@lru_cache(maxsize=8)
def _cached_vector_store(settings: RAGSettings) -> Chroma:
    return build_vector_store(settings=settings)


def _vector_search(
    query: str,
    settings: RAGSettings,
    source_type: str,
) -> list[RankedDocument]:
    store = _get_synced_store(settings)
    matches = store.similarity_search_with_score(
        query,
        k=settings.candidate_k,
        filter={"source_type": source_type},
    )
    results: list[RankedDocument] = []
    for rank, (document, distance) in enumerate(matches, start=1):
        score = 1.0 - float(distance)
        if score < settings.score_threshold:
            continue
        results.append(
            RankedDocument(
                document=document,
                score=max(0.0, min(1.0, score)),
                rank=rank,
            )
        )
    return results


def _serialize_candidate(
    candidate: FusedCandidate,
    *,
    query: str,
    source_type: str,
    rank: int,
    retrieval_method: str,
    rerank_method: str,
    retrieval_warnings: list[str],
) -> dict:
    document = candidate.document
    chunk_id = candidate.chunk_id
    serialized = {
        "source_type": source_type,
        "source": document.metadata.get("source", "unknown"),
        "section": document.metadata.get("section", "document"),
        "section_path": document.metadata.get("section_path", "document"),
        "parent_id": document.metadata.get("parent_id", "unknown"),
        "chunk_id": chunk_id,
        "rank": rank,
        "score": round(max(0.0, min(1.0, candidate.rerank_score)), 4),
        "vector_score": _rounded(candidate.vector_score),
        "vector_rank": candidate.vector_rank,
        "bm25_score": _rounded(candidate.bm25_score),
        "bm25_rank": candidate.bm25_rank,
        "fusion_score": round(candidate.fusion_score, 6),
        "rerank_score": round(candidate.rerank_score, 4),
        "snippet": content_snippet(document.page_content),
        "content": document.page_content.strip(),
        "retrieval_method": retrieval_method,
        "rerank_method": rerank_method,
        "retrieval_warnings": retrieval_warnings,
    }
    if source_type == "doc":
        serialized["evidence_id"] = f"doc:{chunk_id}"
    elif source_type == "bug":
        bug_id = str(document.metadata.get("bug_id", document.metadata.get("source")))
        serialized.update(
            {
                "evidence_id": f"bug:{bug_id}",
                "bug_id": bug_id,
                "title": document.metadata.get("title", ""),
                "module": document.metadata.get("module", ""),
                "symptom": document.metadata.get("symptom", ""),
                "root_cause": document.metadata.get("root_cause", ""),
                "fix": document.metadata.get("fix", ""),
                "keywords": _json_list(document.metadata.get("keywords_json")),
                "related_files": _json_list(
                    document.metadata.get("related_files_json")
                ),
            }
        )
    elif source_type == "code":
        raw_content = _code_content(document)
        start_line = int(document.metadata.get("start_line", 1))
        line, snippet, matched_terms = _locate_code(
            query,
            raw_content,
            base_line=start_line,
        )
        file_name = str(document.metadata.get("source", "unknown"))
        serialized.update(
            {
                "evidence_id": f"code:{file_name}:{line}",
                "file": file_name,
                "path": document.metadata.get("path", file_name),
                "line": line,
                "symbol": document.metadata.get("symbol", "source_file"),
                "start_line": start_line,
                "end_line": int(document.metadata.get("end_line", start_line)),
                "snippet": snippet,
                "matched_terms": matched_terms,
                "content": raw_content.strip(),
                "code_kind": document.metadata.get("code_kind", "source_file"),
                "calls": _json_list(document.metadata.get("calls_json")),
                "callers": _json_list(document.metadata.get("callers_json")),
                "preprocessor_context": document.metadata.get(
                    "preprocessor_context",
                    "",
                ),
                "repository_revision": document.metadata.get(
                    "repository_revision",
                    "",
                ),
                "commit_sha": document.metadata.get("commit_sha"),
                "commit_subject": document.metadata.get("commit_subject"),
                "commit_date": document.metadata.get("commit_date"),
                "changed_files": _json_list(
                    document.metadata.get("changed_files_json")
                ),
            }
        )
    else:  # pragma: no cover - guarded by corpus source validation
        raise ValueError(f"Unsupported source type: {source_type}")
    return serialized


def _retrieval_method(
    vector_results: list[RankedDocument],
    bm25_results: list[RankedDocument],
    rerank_method: str,
) -> str:
    if vector_results and bm25_results:
        method = "hybrid_rrf"
    elif vector_results:
        method = "vector"
    else:
        method = "bm25"
    if rerank_method != "none":
        return f"{method}_rerank"
    return method


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(float(value), 4)


def content_snippet(content: str, limit: int = 420) -> str:
    lines: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            if lines:
                break
            continue
        if _MARKDOWN_HEADING.match(stripped):
            if lines:
                break
            continue
        lines.append(stripped)

    snippet = " ".join(lines)
    if not snippet:
        snippet = next(
            (line.strip() for line in content.splitlines() if line.strip()),
            "",
        )
    if len(snippet) <= limit:
        return snippet
    return snippet[: limit - 3].rstrip() + "..."


def _json_list(value: object) -> list[str]:
    if not isinstance(value, str):
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _locate_code(
    query: str,
    content: str,
    radius: int = 2,
    base_line: int = 1,
) -> tuple[int, str, list[str]]:
    from app.rag.ranking import tokenize_for_retrieval

    query_tokens = set(tokenize_for_retrieval(query))
    lines = content.splitlines()
    if not lines:
        return 1, "", []
    scored = []
    for index, line in enumerate(lines):
        matched = query_tokens & set(tokenize_for_retrieval(line))
        scored.append((len(matched), -index, index, matched))
    _, _, best_index, matched = max(scored)
    start = max(0, best_index - radius)
    end = min(len(lines), best_index + radius + 1)
    return base_line + best_index, "\n".join(lines[start:end]), sorted(matched)


def _code_content(document: Document) -> str:
    header_lines = int(document.metadata.get("search_header_lines", 0))
    lines = document.page_content.splitlines()
    return "\n".join(lines[header_lines:])
