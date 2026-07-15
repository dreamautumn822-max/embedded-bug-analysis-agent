from langchain_core.documents import Document

from app.rag.ranking import (
    RankedDocument,
    bm25_search,
    reciprocal_rank_fusion,
    tokenize_for_retrieval,
)


def _doc(chunk_id: str, content: str) -> Document:
    return Document(
        page_content=content,
        metadata={"chunk_id": chunk_id, "source": f"{chunk_id}.md"},
    )


def test_retrieval_tokenizer_keeps_identifiers_and_cjk_ngrams():
    tokens = tokenize_for_retrieval("PPPoE retry_timer 异常后无法重新拨号")

    assert "pppoe" in tokens
    assert "retry_timer" in tokens
    assert "拨号" in tokens


def test_bm25_search_prioritizes_exact_log_and_module_terms():
    documents = [
        _doc("dhcp", "DHCP lease allocation failed because br-lan is not ready"),
        _doc("wifi", "Wi-Fi station disconnected during channel switch"),
        _doc("tr069", "TR-069 Inform failed while contacting ACS"),
    ]

    results = bm25_search("dhcp lease allocation failed", documents, k=3)

    assert results[0].document.metadata["chunk_id"] == "dhcp"
    assert results[0].rank == 1
    assert results[0].score > results[1].score


def test_rrf_rewards_candidates_recalled_by_both_paths():
    shared = _doc("shared", "shared result")
    vector_only = _doc("vector", "vector result")
    bm25_only = _doc("bm25", "bm25 result")

    fused = reciprocal_rank_fusion(
        [
            RankedDocument(vector_only, score=0.9, rank=1),
            RankedDocument(shared, score=0.8, rank=2),
        ],
        [
            RankedDocument(bm25_only, score=8.0, rank=1),
            RankedDocument(shared, score=7.0, rank=2),
        ],
        rrf_k=60,
        vector_weight=1.0,
        bm25_weight=1.0,
    )

    assert fused[0].chunk_id == "shared"
    assert fused[0].vector_rank == 2
    assert fused[0].bm25_rank == 2
    assert fused[0].fusion_score > fused[1].fusion_score
