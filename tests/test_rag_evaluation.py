import pytest

from app.rag.evaluation import aggregate_ranking_metrics, evaluate_ranking


def test_evaluate_ranking_calculates_standard_metrics():
    result = evaluate_ranking(
        ["irrelevant", "doc-b", "doc-a"],
        ["doc-a", "doc-b"],
        k=3,
    )

    assert result["recall_at_k"] == 1.0
    assert result["precision_at_k"] == pytest.approx(2 / 3)
    assert result["hit_rate_at_k"] == 1.0
    assert result["mrr"] == 0.5
    assert result["ndcg_at_k"] < 1.0
    assert result["matched_ids"] == ["doc-b", "doc-a"]


def test_evaluate_ranking_deduplicates_retrieved_ids():
    result = evaluate_ranking(["doc-a", "doc-a", "other"], ["doc-a"], k=2)

    assert result["retrieved_count"] == 2
    assert result["recall_at_k"] == 1.0
    assert result["precision_at_k"] == 0.5
    assert result["mrr"] == 1.0


@pytest.mark.parametrize(
    ("retrieved", "relevant", "k"),
    [([], ["doc-a"], 0), ([], [], 1)],
)
def test_evaluate_ranking_rejects_invalid_inputs(retrieved, relevant, k):
    with pytest.raises(ValueError):
        evaluate_ranking(retrieved, relevant, k=k)


def test_aggregate_ranking_metrics_averages_cases():
    first = evaluate_ranking(["doc-a"], ["doc-a"], k=1)
    second = evaluate_ranking(["other"], ["doc-b"], k=1)

    summary = aggregate_ranking_metrics([first, second])

    assert summary == {
        "recall_at_k": 0.5,
        "precision_at_k": 0.5,
        "hit_rate_at_k": 0.5,
        "mrr": 0.5,
        "ndcg_at_k": 0.5,
    }
