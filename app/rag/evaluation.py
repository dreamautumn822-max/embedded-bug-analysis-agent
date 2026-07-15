import math
from collections.abc import Iterable


def evaluate_ranking(
    retrieved_ids: Iterable[str],
    relevant_ids: Iterable[str],
    *,
    k: int,
) -> dict:
    if k < 1:
        raise ValueError("k must be >= 1")

    relevant = set(relevant_ids)
    if not relevant:
        raise ValueError("relevant_ids must not be empty")

    retrieved = _unique(list(retrieved_ids))[:k]
    matched = [item for item in retrieved if item in relevant]
    first_relevant_rank = next(
        (rank for rank, item in enumerate(retrieved, start=1) if item in relevant),
        None,
    )

    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, item in enumerate(retrieved, start=1)
        if item in relevant
    )
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))

    return {
        "recall_at_k": len(matched) / len(relevant),
        "precision_at_k": len(matched) / k,
        "hit_rate_at_k": float(bool(matched)),
        "mrr": 0.0 if first_relevant_rank is None else 1.0 / first_relevant_rank,
        "ndcg_at_k": 0.0 if idcg == 0 else dcg / idcg,
        "retrieved_count": len(retrieved),
        "relevant_count": len(relevant),
        "matched_ids": matched,
    }


def aggregate_ranking_metrics(results: list[dict]) -> dict[str, float]:
    if not results:
        raise ValueError("results must not be empty")

    metric_names = (
        "recall_at_k",
        "precision_at_k",
        "hit_rate_at_k",
        "mrr",
        "ndcg_at_k",
    )
    return {
        name: sum(float(result[name]) for result in results) / len(results)
        for name in metric_names
    }


def _unique(values: list[str]) -> list[str]:
    unique_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values
