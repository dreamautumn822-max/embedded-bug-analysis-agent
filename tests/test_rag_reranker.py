from langchain_core.documents import Document

from app.rag.ranking import FusedCandidate
from app.rag.reranker import rerank_candidates, warmup_model_reranker


def _candidate(
    chunk_id: str,
    section: str,
    content: str,
    *,
    fusion_score: float,
) -> FusedCandidate:
    return FusedCandidate(
        document=Document(
            page_content=content,
            metadata={
                "chunk_id": chunk_id,
                "source": "pppoe.md",
                "section": section,
                "section_path": f"PPPoE > {section}",
            },
        ),
        vector_score=0.5,
        vector_rank=1,
        bm25_score=5.0,
        bm25_rank=1,
        fusion_score=fusion_score,
    )


def test_local_reranker_uses_section_signals_instead_of_document_length():
    long_generic = _candidate(
        "mtu",
        "MTU 与现场排查",
        "PPPoE MTU 排查需要采集 WAN link、retry timer 和状态机日志。" * 4,
        fusion_score=0.033,
    )
    exact_section = _candidate(
        "link-flap",
        "Link flap 与重试定时器",
        "WAN link flap 后必须重新启动 retry timer。",
        fusion_score=0.032,
    )

    ranked, method = rerank_candidates(
        "WAN link flap 后 PPPoE retry timer 没有启动",
        [long_generic, exact_section],
        provider="local",
        model_name="unused",
        rerank_weight=0.65,
    )

    assert method == "local_feature"
    assert ranked[0].chunk_id == "link-flap"
    assert ranked[0].rerank_score > ranked[1].rerank_score


def test_cross_encoder_reranker_uses_model_pair_scores(monkeypatch):
    class FakeCrossEncoder:
        def predict(self, pairs, show_progress_bar):
            assert len(pairs) == 2
            assert show_progress_bar is False
            return [0.1, 0.9]

    monkeypatch.setattr(
        "app.rag.reranker._load_cross_encoder",
        lambda model_name: FakeCrossEncoder(),
    )
    first = _candidate("first", "普通章节", "普通内容", fusion_score=0.04)
    second = _candidate("second", "目标章节", "目标内容", fusion_score=0.03)

    ranked, method = rerank_candidates(
        "目标查询",
        [first, second],
        provider="cross_encoder",
        model_name="fake-model",
        rerank_weight=0.8,
    )

    assert method == "cross_encoder"
    assert ranked[0].chunk_id == "second"


def test_flashrank_reranker_uses_model_scores(monkeypatch, tmp_path):
    class FakeFlashRanker:
        def rerank(self, request):
            assert request.query == "目标查询"
            return [
                {"id": "second", "score": 0.9},
                {"id": "first", "score": 0.1},
            ]

    monkeypatch.setattr(
        "app.rag.reranker._load_flashrank",
        lambda model_name, cache_dir, max_length: FakeFlashRanker(),
    )
    first = _candidate("first", "普通章节", "普通内容", fusion_score=0.04)
    second = _candidate("second", "目标章节", "目标内容", fusion_score=0.03)

    ranked, method = rerank_candidates(
        "目标查询",
        [first, second],
        provider="flashrank",
        model_name="fake-model",
        rerank_weight=0.8,
        cache_dir=tmp_path,
        max_length=128,
    )

    assert method == "flashrank"
    assert ranked[0].chunk_id == "second"


def test_model_reranker_warmup_dispatches_to_flashrank(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        "app.rag.reranker._load_flashrank",
        lambda model_name, cache_dir, max_length: calls.append(
            (model_name, cache_dir, max_length)
        ),
    )

    warmup_model_reranker(
        provider="flashrank",
        model_name="test-model",
        cache_dir=tmp_path,
        max_length=128,
    )

    assert calls == [("test-model", str(tmp_path), 128)]
