import os
from dataclasses import dataclass
from pathlib import Path

from app.paths import BUG_HISTORY_PATH, CODEBASE_DIR, PROJECT_ROOT
from app.rag.splitter import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE


SUPPORTED_EMBEDDING_PROVIDERS = {"local", "fastembed", "openai"}
SUPPORTED_RETRIEVAL_MODES = {"vector", "bm25", "hybrid"}
SUPPORTED_RERANK_PROVIDERS = {"none", "local", "flashrank", "cross_encoder"}


@dataclass(frozen=True)
class RAGSettings:
    docs_dir: Path
    persist_dir: Path
    embedding_provider: str
    embedding_model: str
    embedding_base_url: str | None
    embedding_api_key: str | None
    embedding_dimensions: int
    top_k: int
    score_threshold: float
    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    retrieval_mode: str = "hybrid"
    candidate_k: int = 8
    rrf_k: int = 60
    vector_weight: float = 1.0
    bm25_weight: float = 1.0
    rerank_provider: str = "local"
    rerank_model: str = "ms-marco-MultiBERT-L-12"
    rerank_weight: float = 0.65
    rerank_cache_dir: Path = PROJECT_ROOT / ".cache" / "rerank"
    rerank_max_length: int = 256
    embedding_cache_dir: Path = PROJECT_ROOT / ".cache" / "embeddings"
    embedding_max_length: int = 512
    embedding_threads: int | None = None
    bug_history_path: Path = BUG_HISTORY_PATH
    codebase_dir: Path = CODEBASE_DIR
    git_history_enabled: bool = False
    git_max_commits: int = 20
    git_diff_max_chars: int = 12000

    @classmethod
    def from_env(cls) -> "RAGSettings":
        provider = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()
        if provider not in SUPPORTED_EMBEDDING_PROVIDERS:
            supported = ", ".join(sorted(SUPPORTED_EMBEDDING_PROVIDERS))
            raise ValueError(f"EMBEDDING_PROVIDER must be one of: {supported}")

        default_models = {
            "local": "local-hashing-v1",
            "fastembed": "BAAI/bge-small-zh-v1.5",
            "openai": "text-embedding-3-small",
        }
        default_model = default_models[provider]
        dimensions = _positive_int_env("EMBEDDING_DIMENSIONS", 1024)
        if provider == "local" and dimensions < 64:
            raise ValueError("EMBEDDING_DIMENSIONS must be >= 64 for local embeddings")
        top_k = _positive_int_env("RAG_TOP_K", 3)
        score_threshold = _bounded_float_env("RAG_SCORE_THRESHOLD", 0.1, 0.0, 1.0)
        chunk_size = _positive_int_env("RAG_CHUNK_SIZE", DEFAULT_CHUNK_SIZE)
        chunk_overlap = _non_negative_int_env("RAG_CHUNK_OVERLAP", DEFAULT_CHUNK_OVERLAP)
        if chunk_overlap >= chunk_size:
            raise ValueError("RAG_CHUNK_OVERLAP must be smaller than RAG_CHUNK_SIZE")
        retrieval_mode = _choice_env(
            "RAG_RETRIEVAL_MODE",
            "hybrid",
            SUPPORTED_RETRIEVAL_MODES,
        )
        candidate_k = _positive_int_env("RAG_CANDIDATE_K", max(8, top_k))
        if candidate_k < top_k:
            raise ValueError("RAG_CANDIDATE_K must be >= RAG_TOP_K")
        rerank_provider = _choice_env(
            "RAG_RERANK_PROVIDER",
            "local",
            SUPPORTED_RERANK_PROVIDERS,
        )
        default_rerank_model = (
            "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
            if rerank_provider == "cross_encoder"
            else "ms-marco-MultiBERT-L-12"
        )
        vector_weight = _bounded_float_env("RAG_VECTOR_WEIGHT", 1.0, 0.0, 10.0)
        bm25_weight = _bounded_float_env("RAG_BM25_WEIGHT", 1.0, 0.0, 10.0)
        if retrieval_mode in {"vector", "hybrid"} and vector_weight == 0:
            raise ValueError("RAG_VECTOR_WEIGHT must be > 0 for vector retrieval")
        if retrieval_mode in {"bm25", "hybrid"} and bm25_weight == 0:
            raise ValueError("RAG_BM25_WEIGHT must be > 0 for BM25 retrieval")

        return cls(
            docs_dir=_project_path_env("DOCS_DIR", "data/docs"),
            persist_dir=_project_path_env("CHROMA_DIR", ".chroma"),
            embedding_provider=provider,
            embedding_model=os.getenv("EMBEDDING_MODEL", default_model).strip() or default_model,
            embedding_base_url=_optional_env("EMBEDDING_BASE_URL"),
            embedding_api_key=_optional_env("EMBEDDING_API_KEY"),
            embedding_dimensions=dimensions,
            top_k=top_k,
            score_threshold=score_threshold,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            retrieval_mode=retrieval_mode,
            candidate_k=candidate_k,
            rrf_k=_positive_int_env("RAG_RRF_K", 60),
            vector_weight=vector_weight,
            bm25_weight=bm25_weight,
            rerank_provider=rerank_provider,
            rerank_model=(
                os.getenv(
                    "RAG_RERANK_MODEL",
                    default_rerank_model,
                ).strip()
                or default_rerank_model
            ),
            rerank_weight=_bounded_float_env("RAG_RERANK_WEIGHT", 0.65, 0.0, 1.0),
            rerank_cache_dir=_project_path_env("RAG_RERANK_CACHE_DIR", ".cache/rerank"),
            rerank_max_length=_positive_int_env("RAG_RERANK_MAX_LENGTH", 256),
            embedding_cache_dir=_project_path_env(
                "EMBEDDING_CACHE_DIR",
                ".cache/embeddings",
            ),
            embedding_max_length=_bounded_int_env(
                "EMBEDDING_MAX_LENGTH",
                512,
                1,
                512,
            ),
            embedding_threads=_optional_positive_int_env("EMBEDDING_THREADS"),
            bug_history_path=_project_path_env(
                "BUG_HISTORY_PATH",
                "data/bugs/bug_history.json",
            ),
            codebase_dir=_project_path_env("CODEBASE_DIR", "data/codebase"),
            git_history_enabled=_bool_env("RAG_GIT_HISTORY_ENABLED", False),
            git_max_commits=_positive_int_env("RAG_GIT_MAX_COMMITS", 20),
            git_diff_max_chars=_positive_int_env("RAG_GIT_DIFF_MAX_CHARS", 12000),
        )


def _project_path_env(name: str, default: str) -> Path:
    path = Path(os.getenv(name, default)).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _choice_env(name: str, default: str, supported: set[str]) -> str:
    value = os.getenv(name, default).strip().lower()
    if value not in supported:
        choices = ", ".join(sorted(supported))
        raise ValueError(f"{name} must be one of: {choices}")
    return value


def _positive_int_env(name: str, default: int) -> int:
    value = _optional_env(name)
    parsed = default if value is None else int(value)
    if parsed < 1:
        raise ValueError(f"{name} must be >= 1")
    return parsed


def _optional_positive_int_env(name: str) -> int | None:
    value = _optional_env(name)
    if value is None:
        return None
    parsed = int(value)
    if parsed < 1:
        raise ValueError(f"{name} must be >= 1")
    return parsed


def _bounded_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    value = _optional_env(name)
    parsed = default if value is None else int(value)
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _non_negative_int_env(name: str, default: int) -> int:
    value = _optional_env(name)
    parsed = default if value is None else int(value)
    if parsed < 0:
        raise ValueError(f"{name} must be >= 0")
    return parsed


def _bounded_float_env(name: str, default: float, minimum: float, maximum: float) -> float:
    value = _optional_env(name)
    parsed = default if value is None else float(value)
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _bool_env(name: str, default: bool) -> bool:
    value = _optional_env(name)
    if value is None:
        return default
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")
