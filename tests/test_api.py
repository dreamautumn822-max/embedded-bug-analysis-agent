from fastapi.testclient import TestClient

from app.main import app
from app.rag.retriever import clear_vector_store_cache


def test_analyze_endpoint_returns_dhcp_report():
    client = TestClient(app)
    logs = "\n".join(
        [
            "2026-06-25 14:03:11 netifd: interface lan reload",
            "2026-06-25 14:03:12 kernel: br-lan port state changed to blocking",
            "2026-06-25 14:03:12 dhcpd: lease allocation failed",
            "2026-06-25 14:03:14 kernel: br-lan port state changed to forwarding",
        ]
    )

    response = client.post(
        "/analyze",
        json={
            "device_model": "AX3000 Router",
            "firmware_version": "v2.1.8",
            "symptom": "升级后 DHCP 客户端偶发获取不到 IP",
            "logs": logs,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["bug_type"] == "network_dhcp"
    assert "DHCP" in data["summary"]
    assert data["confidence"] >= 0.75
    assert any("BUG-018" in item or item.startswith("log: ") for item in data["evidence"])
    assert data["evidence_details"]
    assert data["hypotheses"][0]["evidence_ids"]
    assert set(data["hypotheses"][0]["evidence_ids"]) <= {
        item["evidence_id"] for item in data["evidence_details"]
    }
    doc_evidence = next(
        item for item in data["evidence_details"] if item["evidence_type"] == "doc"
    )
    assert doc_evidence["retrieval_method"] == "hybrid_rrf_rerank"
    assert doc_evidence["rerank_method"] == "local_feature"
    assert doc_evidence["vector_rank"] is not None
    assert doc_evidence["bm25_rank"] is not None
    assert data["generation_mode"] in {"llm", "rule"}
    assert data["trace_events"]
    assert data["review_status"] == "not_required"


def test_reviewable_analysis_api_pauses_and_accepts_review(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv(
        "LANGGRAPH_CHECKPOINT_PATH",
        str(tmp_path / "checkpoints.sqlite"),
    )
    clear_vector_store_cache()
    client = TestClient(app)

    created = client.post(
        "/analyses",
        json={
            "device_model": "Unknown Gateway",
            "firmware_version": "v0.0.1",
            "symptom": "设备出现无法识别的随机异常",
            "logs": "daemon: unexplained status code 777",
        },
    )

    assert created.status_code == 200
    pending = created.json()
    assert pending["status"] == "pending_review"
    assert pending["review_payload"]["kind"] == "bug_analysis_review"
    assert pending["result"] is None

    fetched = client.get(f"/analyses/{pending['analysis_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "pending_review"

    reviewed = client.post(
        f"/analyses/{pending['analysis_id']}/review",
        json={
            "approved": True,
            "reviewer": "qa-owner",
            "comment": "已补充现场信息",
        },
    )
    assert reviewed.status_code == 200
    completed = reviewed.json()
    assert completed["status"] == "completed"
    assert completed["review_status"] == "approved"
    assert completed["result"]["review_decision"]["reviewer"] == "qa-owner"

    duplicate = client.post(
        f"/analyses/{pending['analysis_id']}/review",
        json={"approved": True, "reviewer": "qa-owner"},
    )
    assert duplicate.status_code == 409


def test_reviewable_analysis_api_returns_404_for_unknown_id(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "LANGGRAPH_CHECKPOINT_PATH",
        str(tmp_path / "missing.sqlite"),
    )
    response = TestClient(app).get("/analyses/does-not-exist")

    assert response.status_code == 404
