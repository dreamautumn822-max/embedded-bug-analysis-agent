import re
from functools import lru_cache
from pathlib import Path

from app.rag.ranking import FusedCandidate, tokenize_for_retrieval


class RerankerError(RuntimeError):
    """Raised when the configured model reranker cannot produce scores."""


_IDENTIFIER_PATTERN = re.compile(r"[a-zA-Z0-9]+(?:[._:/-][a-zA-Z0-9]+)*")


def warmup_model_reranker(
    *,
    provider: str,
    model_name: str,
    cache_dir: Path | str,
    max_length: int,
) -> None:
    if provider == "flashrank":
        _load_flashrank(model_name, str(cache_dir), max_length)
        return
    if provider == "cross_encoder":
        _load_cross_encoder(model_name)
        return
    raise ValueError("warmup only supports flashrank or cross_encoder")


def rerank_candidates(
    query: str,
    candidates: list[FusedCandidate],
    *,
    provider: str,
    model_name: str,
    rerank_weight: float,
    cache_dir: Path | str = "/tmp",
    max_length: int = 256,
) -> tuple[list[FusedCandidate], str]:
    if not candidates:
        return [], "none"
    if provider == "none":
        return _rank_by_fusion(candidates), "none"
    if provider == "local":
        return _local_feature_rerank(query, candidates, rerank_weight), "local_feature"
    if provider == "flashrank":
        return _flashrank_rerank(
            query,
            candidates,
            model_name=model_name,
            rerank_weight=rerank_weight,
            cache_dir=cache_dir,
            max_length=max_length,
        ), "flashrank"
    if provider == "cross_encoder":
        return _cross_encoder_rerank(
            query,
            candidates,
            model_name=model_name,
            rerank_weight=rerank_weight,
        ), "cross_encoder"
    raise ValueError(f"Unsupported rerank provider: {provider}")


def _flashrank_rerank(
    query: str,
    candidates: list[FusedCandidate],
    *,
    model_name: str,
    rerank_weight: float,
    cache_dir: Path | str,
    max_length: int,
) -> list[FusedCandidate]:
    try:
        from flashrank import RerankRequest

        ranker = _load_flashrank(model_name, str(cache_dir), max_length)
        results = ranker.rerank(
            RerankRequest(
                query=query,
                passages=[
                    {
                        "id": candidate.chunk_id,
                        "text": candidate.document.page_content,
                    }
                    for candidate in candidates
                ],
            )
        )
        score_by_id = {str(result["id"]): float(result["score"]) for result in results}
        model_scores = _min_max(
            [score_by_id[candidate.chunk_id] for candidate in candidates]
        )
    except Exception as exc:
        raise RerankerError(f"FlashRank rerank failed: {exc}") from exc

    fusion_scores = _relative_to_max(
        [candidate.fusion_score for candidate in candidates]
    )
    for index, candidate in enumerate(candidates):
        candidate.rerank_score = (
            rerank_weight * model_scores[index]
            + (1.0 - rerank_weight) * fusion_scores[index]
        )
    return _sort_by_rerank_score(candidates)


def _local_feature_rerank(
    query: str,
    candidates: list[FusedCandidate],
    rerank_weight: float,
) -> list[FusedCandidate]:
    query_tokens = set(tokenize_for_retrieval(query))
    query_identifiers = {
        token.lower() for token in _IDENTIFIER_PATTERN.findall(query) if len(token) >= 3
    }
    fusion_scores = _relative_to_max(
        [candidate.fusion_score for candidate in candidates]
    )
    bm25_scores = _min_max(
        [max(0.0, candidate.bm25_score or 0.0) for candidate in candidates]
    )

    for index, candidate in enumerate(candidates):
        content_tokens = set(tokenize_for_retrieval(candidate.document.page_content))
        metadata_text = " ".join(
            str(candidate.document.metadata.get(key, ""))
            for key in ("source", "section", "section_path")
        )
        metadata_tokens = set(tokenize_for_retrieval(metadata_text))
        content_identifiers = {
            token.lower()
            for token in _IDENTIFIER_PATTERN.findall(candidate.document.page_content)
        }
        metadata_identifiers = {
            token.lower() for token in _IDENTIFIER_PATTERN.findall(metadata_text)
        }

        coverage = _coverage(query_tokens, content_tokens)
        section_coverage = _coverage(query_tokens, metadata_tokens)
        section_precision = _coverage(metadata_tokens, query_tokens)
        identifier_coverage = _coverage(query_identifiers, content_identifiers)
        metadata_identifier_coverage = _coverage(
            query_identifiers,
            metadata_identifiers,
        )
        vector_score = max(0.0, min(1.0, candidate.vector_score or 0.0))
        feature_score = (
            0.20 * coverage
            + 0.10 * identifier_coverage
            + 0.05 * section_coverage
            + 0.25 * section_precision
            + 0.15 * metadata_identifier_coverage
            + 0.10 * bm25_scores[index]
            + 0.15 * vector_score
        )
        candidate.rerank_score = (
            rerank_weight * feature_score
            + (1.0 - rerank_weight) * fusion_scores[index]
        )

    return _sort_by_rerank_score(candidates)


def _cross_encoder_rerank(
    query: str,
    candidates: list[FusedCandidate],
    *,
    model_name: str,
    rerank_weight: float,
) -> list[FusedCandidate]:
    try:
        model = _load_cross_encoder(model_name)
        scores = model.predict(
            [[query, candidate.document.page_content] for candidate in candidates],
            show_progress_bar=False,
        )
        model_scores = _min_max([_as_float(score) for score in scores])
    except Exception as exc:
        raise RerankerError(f"CrossEncoder rerank failed: {exc}") from exc

    fusion_scores = _relative_to_max(
        [candidate.fusion_score for candidate in candidates]
    )
    for index, candidate in enumerate(candidates):
        candidate.rerank_score = (
            rerank_weight * model_scores[index]
            + (1.0 - rerank_weight) * fusion_scores[index]
        )
    return _sort_by_rerank_score(candidates)


@lru_cache(maxsize=2)
def _load_cross_encoder(model_name: str):
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise RerankerError(
            "sentence-transformers is required for RAG_RERANK_PROVIDER=cross_encoder"
        ) from exc
    return CrossEncoder(model_name)


@lru_cache(maxsize=2)
def _load_flashrank(model_name: str, cache_dir: str, max_length: int):
    try:
        from flashrank import Ranker
    except ImportError as exc:
        raise RerankerError(
            "flashrank is required for RAG_RERANK_PROVIDER=flashrank"
        ) from exc
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    return Ranker(
        model_name=model_name,
        cache_dir=cache_dir,
        max_length=max_length,
        log_level="WARNING",
    )


def _rank_by_fusion(candidates: list[FusedCandidate]) -> list[FusedCandidate]:
    normalized = _relative_to_max(
        [candidate.fusion_score for candidate in candidates]
    )
    for candidate, score in zip(candidates, normalized, strict=True):
        candidate.rerank_score = score
    return _sort_by_rerank_score(candidates)


def _sort_by_rerank_score(
    candidates: list[FusedCandidate],
) -> list[FusedCandidate]:
    return sorted(
        candidates,
        key=lambda candidate: (-candidate.rerank_score, candidate.chunk_id),
    )


def _coverage(expected: set[str], actual: set[str]) -> float:
    if not expected:
        return 0.0
    return len(expected & actual) / len(expected)


def _min_max(values: list[float]) -> list[float]:
    if not values:
        return []
    minimum = min(values)
    maximum = max(values)
    if maximum == minimum:
        return [1.0 if maximum > 0 else 0.0 for _ in values]
    return [(value - minimum) / (maximum - minimum) for value in values]


def _relative_to_max(values: list[float]) -> list[float]:
    if not values:
        return []
    maximum = max(values)
    if maximum <= 0:
        return [0.0 for _ in values]
    return [max(0.0, value) / maximum for value in values]


def _as_float(value) -> float:
    if hasattr(value, "item"):
        return float(value.item())
    if isinstance(value, (list, tuple)) and len(value) == 1:
        return float(value[0])
    return float(value)
