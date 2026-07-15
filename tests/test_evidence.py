from app.evidence import (
    bind_hypothesis_evidence,
    build_evidence_details,
    format_evidence,
)


def _state() -> dict:
    return {
        "parsed_logs": {"evidence": ["dhcpd: lease allocation failed"]},
        "related_docs": [
            {
                "source": "dhcp.md",
                "section": "启动依赖与时序",
                "chunk_id": "dhcp.md::启动依赖与时序::000",
                "evidence_id": "doc:dhcp.md::启动依赖与时序::000",
                "snippet": "DHCP server 必须等待 bridge ready。",
                "score": 0.91,
                "rank": 1,
                "retrieval_method": "hybrid_rrf_rerank",
                "rerank_method": "local_feature",
                "vector_score": 0.82,
                "vector_rank": 2,
                "bm25_score": 6.2,
                "bm25_rank": 1,
                "fusion_score": 0.0325,
                "rerank_score": 0.91,
            }
        ],
        "related_bugs": [
            {
                "bug_id": "BUG-018",
                "root_cause": "DHCP starts before bridge ready",
            }
        ],
        "related_code": [
            {
                "file": "netifd_reload.c",
                "line": 3,
                "symbol": "lan_reload_handler",
                "start_line": 3,
                "end_line": 6,
                "snippet": "restart_dhcp_server();",
            }
        ],
    }


def test_build_evidence_details_creates_stable_typed_ids():
    first = build_evidence_details(_state())
    repeated = build_evidence_details(_state())

    assert first == repeated
    assert {item["evidence_type"] for item in first} == {
        "log",
        "doc",
        "bug",
        "code",
    }
    assert {item["evidence_id"] for item in first} >= {
        "doc:dhcp.md::启动依赖与时序::000",
        "bug:BUG-018",
        "code:netifd_reload.c:3",
    }
    assert all(format_evidence(item).startswith(f"{item['evidence_type']}: ") for item in first)
    doc = next(item for item in first if item["evidence_type"] == "doc")
    assert doc["retrieval_method"] == "hybrid_rrf_rerank"
    assert doc["vector_rank"] == 2
    assert doc["bm25_rank"] == 1
    assert doc["rerank_score"] == 0.91
    code = next(item for item in first if item["evidence_type"] == "code")
    assert code["symbol"] == "lan_reload_handler"
    assert code["section"] == "lan_reload_handler"
    assert code["start_line"] == 3
    assert code["end_line"] == 6


def test_bind_hypothesis_evidence_filters_unknown_ids():
    details = build_evidence_details(_state())
    hypotheses = [
        {
            "title": "DHCP 启动时序异常",
            "description": "bridge 未 ready 时启动 DHCP。",
            "confidence": 0.9,
            "evidence_ids": ["bug:BUG-018", "made-up-id"],
        }
    ]

    bound = bind_hypothesis_evidence(hypotheses, details)

    assert bound[0]["evidence_ids"] == ["bug:BUG-018"]


def test_bind_hypothesis_evidence_uses_representative_fallback():
    details = build_evidence_details(_state())
    hypotheses = [
        {
            "title": "DHCP 启动时序异常",
            "description": "bridge 未 ready 时启动 DHCP。",
            "confidence": 0.9,
        }
    ]

    bound = bind_hypothesis_evidence(hypotheses, details)

    assert len(bound[0]["evidence_ids"]) == 4
    assert set(bound[0]["evidence_ids"]) <= {
        item["evidence_id"] for item in details
    }
