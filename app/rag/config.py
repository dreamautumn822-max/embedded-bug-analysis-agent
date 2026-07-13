import os
from dataclasses import dataclass
from pathlib import Path

from app.paths import PROJECT_ROOT


SUPPORTED_EMBEDDING_PROVIDERS = {"local", "openai"}


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

    @classmethod
    def from_env(cls) -> "RAGSettings":
        provider = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()
        if provider not in SUPPORTED_EMBEDDING_PROVIDERS:
            supported = ", ".join(sorted(SUPPORTED_EMBEDDING_PROVIDERS))
            raise ValueError(f"EMBEDDING_PROVIDER must be one of: {supported}")

        default_model = "local-hashing-v1" if provider == "local" else "text-embedding-3-small"
        dimensions = _positive_int_env("EMBEDDING_DIMENSIONS", 1024)
        if provider == "local" and dimensions < 64:
            raise ValueError("EMBEDDING_DIMENSIONS must be >= 64 for local embeddings")
        top_k = _positive_int_env("RAG_TOP_K", 3)
        score_threshold = _bounded_float_env("RAG_SCORE_THRESHOLD", 0.1, 0.0, 1.0)

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


def _positive_int_env(name: str, default: int) -> int:
    value = _optional_env(name)
    parsed = default if value is None else int(value)
    if parsed < 1:
        raise ValueError(f"{name} must be >= 1")
    return parsed


def _bounded_float_env(name: str, default: float, minimum: float, maximum: float) -> float:
    value = _optional_env(name)
    parsed = default if value is None else float(value)
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed
