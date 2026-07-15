import hashlib
import json
import math
import re
import unicodedata
from dataclasses import replace
from pathlib import Path

from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from app.rag.config import RAGSettings
from app.rag.corpus import CORPUS_VERSION, load_knowledge_chunks
from app.rag.splitter import SPLITTER_VERSION


COLLECTION_PREFIX = "embedded_bug_knowledge"
_LATIN_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[._:/-][a-z0-9]+)*")
_CJK_SEQUENCE_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")


class LocalHashEmbeddings(Embeddings):
    """Deterministic lexical embeddings for offline demos and tests."""

    def __init__(self, dimensions: int = 1024):
        if dimensions < 64:
            raise ValueError("LocalHashEmbeddings dimensions must be >= 64")
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for feature in _text_features(text):
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class FastEmbedLocalEmbeddings(Embeddings):
    """LangChain Embeddings adapter with deterministic Qdrant-cache loading."""

    def __init__(
        self,
        *,
        model_name: str,
        cache_dir: Path,
        max_length: int,
        threads: int | None,
    ):
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:  # pragma: no cover - dependency is pinned
            raise ImportError(
                "fastembed is required when EMBEDDING_PROVIDER=fastembed"
            ) from exc

        cache_dir.mkdir(parents=True, exist_ok=True)
        description = next(
            (
                model
                for model in TextEmbedding.list_supported_models()
                if str(model.get("model", "")).lower() == model_name.lower()
            ),
            None,
        )
        if description is None:
            raise ValueError(f"FastEmbed model is not supported: {model_name}")
        sources = description.get("sources", {})
        model_path: Path | None = None
        if sources.get("url"):
            try:
                model_path = TextEmbedding.retrieve_model_gcs(
                    model_name,
                    str(sources["url"]),
                    str(cache_dir),
                    deprecated_tar_struct=bool(
                        sources.get("_deprecated_tar_struct", False)
                    ),
                    local_files_only=True,
                )
            except Exception:
                model_path = TextEmbedding.retrieve_model_gcs(
                    model_name,
                    str(sources["url"]),
                    str(cache_dir),
                    deprecated_tar_struct=bool(
                        sources.get("_deprecated_tar_struct", False)
                    ),
                )

        kwargs: dict[str, object] = {
            "model_name": model_name,
            "cache_dir": str(cache_dir),
            "max_length": max_length,
            "threads": threads,
        }
        if model_path is not None:
            kwargs["specific_model_path"] = str(model_path)
        self.model = TextEmbedding(**kwargs)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [embedding.tolist() for embedding in self.model.passage_embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return next(self.model.query_embed(text)).tolist()


def build_embeddings(settings: RAGSettings | None = None) -> Embeddings:
    settings = settings or RAGSettings.from_env()
    if settings.embedding_provider == "local":
        return LocalHashEmbeddings(dimensions=settings.embedding_dimensions)

    if settings.embedding_provider == "fastembed":
        return FastEmbedLocalEmbeddings(
            model_name=settings.embedding_model,
            cache_dir=settings.embedding_cache_dir,
            max_length=settings.embedding_max_length,
            threads=settings.embedding_threads,
        )

    if not settings.embedding_api_key:
        raise ValueError("EMBEDDING_API_KEY is required when EMBEDDING_PROVIDER=openai")

    kwargs: dict[str, object] = {
        "model": settings.embedding_model,
        "api_key": settings.embedding_api_key,
    }
    if settings.embedding_base_url:
        kwargs["base_url"] = settings.embedding_base_url
    return OpenAIEmbeddings(**kwargs)


def build_vector_store(
    docs_dir: Path | None = None,
    persist_dir: Path | None = None,
    settings: RAGSettings | None = None,
) -> Chroma:
    settings = settings or RAGSettings.from_env()
    if docs_dir is not None:
        settings = replace(settings, docs_dir=docs_dir.resolve())
    if persist_dir is not None:
        settings = replace(settings, persist_dir=persist_dir.resolve())

    settings.persist_dir.mkdir(parents=True, exist_ok=True)
    store = Chroma(
        collection_name=collection_name(settings),
        embedding_function=build_embeddings(settings),
        persist_directory=str(settings.persist_dir),
        collection_metadata={"hnsw:space": "cosine"},
        client_settings=ChromaSettings(
            anonymized_telemetry=False,
            is_persistent=True,
        ),
    )
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


def sync_vector_store(
    store: Chroma,
    docs_dir: Path,
    *,
    bug_history_path: Path | None = None,
    codebase_dir: Path | None = None,
    chunk_size: int = 300,
    chunk_overlap: int = 50,
    git_history_enabled: bool = False,
    git_max_commits: int = 20,
    git_diff_max_chars: int = 12000,
) -> dict[str, int]:
    documents = [
        _with_content_hash(doc)
        for doc in load_knowledge_chunks(
            docs_dir=docs_dir,
            bug_history_path=bug_history_path,
            codebase_dir=codebase_dir,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            git_history_enabled=git_history_enabled,
            git_max_commits=git_max_commits,
            git_diff_max_chars=git_diff_max_chars,
        )
    ]
    expected = {_document_id(doc): doc for doc in documents}
    current_ids = set(store.get(include=[]).get("ids", []))
    expected_ids = set(expected)

    stale_ids = sorted(current_ids - expected_ids)
    new_ids = sorted(expected_ids - current_ids)
    if stale_ids:
        store.delete(ids=stale_ids)
    if new_ids:
        store.add_documents(
            documents=[expected[doc_id] for doc_id in new_ids],
            ids=new_ids,
        )

    return {
        "added": len(new_ids),
        "deleted": len(stale_ids),
        "total": len(expected_ids),
    }


def collection_name(settings: RAGSettings) -> str:
    identity = json.dumps(
        {
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "base_url": settings.embedding_base_url,
            "docs_dir": str(settings.docs_dir),
            "bug_history_path": str(settings.bug_history_path),
            "codebase_dir": str(settings.codebase_dir),
            "git_history_enabled": settings.git_history_enabled,
            "git_max_commits": settings.git_max_commits,
            "git_diff_max_chars": settings.git_diff_max_chars,
            "corpus_version": CORPUS_VERSION,
            "splitter_version": SPLITTER_VERSION,
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
            "dimensions": settings.embedding_dimensions
            if settings.embedding_provider == "local"
            else None,
        },
        sort_keys=True,
    )
    suffix = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    provider = re.sub(r"[^a-z0-9_-]", "-", settings.embedding_provider.lower())
    return f"{COLLECTION_PREFIX}_{provider}_{suffix}"


def _with_content_hash(document: Document) -> Document:
    content_hash = hashlib.sha256(document.page_content.encode("utf-8")).hexdigest()
    return Document(
        page_content=document.page_content,
        metadata={**document.metadata, "content_hash": content_hash},
    )


def _document_id(document: Document) -> str:
    source = str(document.metadata.get("source", "unknown"))
    chunk_id = str(document.metadata.get("chunk_id", "unknown"))
    content_hash = str(document.metadata["content_hash"])
    digest = hashlib.sha256(
        f"{source}\0{chunk_id}\0{content_hash}".encode("utf-8")
    ).hexdigest()
    return f"chunk-{digest}"


def _text_features(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).lower()
    features = _LATIN_TOKEN_PATTERN.findall(normalized)
    for token in list(features):
        features.extend(
            part for part in re.split(r"[._:/-]+", token) if part != token
        )

    for sequence in _CJK_SEQUENCE_PATTERN.findall(normalized):
        if len(sequence) <= 4:
            features.append(sequence)
        if len(sequence) == 1:
            features.append(sequence)
            continue
        for size in (2, 3):
            if len(sequence) < size:
                continue
            features.extend(
                sequence[index : index + size]
                for index in range(len(sequence) - size + 1)
            )

    return features
