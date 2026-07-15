from pathlib import Path

import pytest

from app.graph.review_workflow import (
    AnalysisNotFoundError,
    AnalysisNotPendingReviewError,
    get_reviewable_analysis,
    resume_reviewable_analysis,
    start_reviewable_analysis,
)
from app.rag.retriever import clear_vector_store_cache


def _configure_offline_runtime(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "chroma"))
    clear_vector_store_cache()


def test_low_confidence_analysis_pauses_and_resumes_from_sqlite(
    monkeypatch,
    tmp_path: Path,
):
    _configure_offline_runtime(monkeypatch, tmp_path)
    checkpoint_path = tmp_path / "checkpoints.sqlite"

    pending = start_reviewable_analysis(
        analysis_id="review-case-001",
        device_model="Unknown Gateway",
        firmware_version="v0.0.1",
        symptom="设备出现无法识别的随机异常",
        logs="daemon: unexplained status code 777",
        checkpoint_path=checkpoint_path,
    )

    assert pending.status == "pending_review"
    assert pending.state["review_status"] == "pending"
    assert pending.review_payload["kind"] == "bug_analysis_review"
    assert pending.review_payload["bug_type"] == "unknown"
    assert pending.review_payload["generation_mode"] == "rule"
    assert pending.state["final_report"] == ""

    persisted = get_reviewable_analysis(
        pending.analysis_id,
        checkpoint_path=checkpoint_path,
    )
    assert persisted.status == "pending_review"

    completed = resume_reviewable_analysis(
        pending.analysis_id,
        approved=False,
        reviewer="qa-owner",
        comment="证据不足，要求补充复现日志",
        checkpoint_path=checkpoint_path,
    )

    assert completed.status == "completed"
    assert completed.state["review_status"] == "rejected"
    assert completed.state["review_decision"]["reviewer"] == "qa-owner"
    assert "结论：驳回" in completed.state["final_report"]
    assert [event["node"] for event in completed.state["trace_events"]].count(
        "extract_bug_info"
    ) == 1
    assert completed.state["trace_events"][-2]["node"] == "queue_human_review"
    assert completed.state["trace_events"][-1]["node"] == "generate_report"

    with pytest.raises(AnalysisNotPendingReviewError):
        resume_reviewable_analysis(
            pending.analysis_id,
            approved=True,
            reviewer="qa-owner",
            checkpoint_path=checkpoint_path,
        )


def test_high_confidence_reviewable_analysis_completes_without_interrupt(
    monkeypatch,
    tmp_path: Path,
):
    _configure_offline_runtime(monkeypatch, tmp_path)

    run = start_reviewable_analysis(
        analysis_id="auto-case-001",
        device_model="AX3000 Router",
        firmware_version="v2.1.8",
        symptom="升级后 DHCP 客户端偶发获取不到 IP",
        logs="dhcpd: lease allocation failed bridge br-lan not ready",
        checkpoint_path=tmp_path / "auto.sqlite",
    )

    assert run.status == "completed"
    assert run.review_payload is None
    assert run.state["review_status"] == "not_required"
    assert run.state["final_report"]


def test_review_workflow_hides_analysis_from_other_tenant(
    monkeypatch,
    tmp_path: Path,
):
    _configure_offline_runtime(monkeypatch, tmp_path)
    checkpoint_path = tmp_path / "tenant-checkpoints.sqlite"
    run = start_reviewable_analysis(
        device_model="Unknown Gateway",
        firmware_version="v0",
        symptom="unknown intermittent issue",
        logs="daemon: unexplained status",
        checkpoint_path=checkpoint_path,
        tenant_id="tenant-a",
    )

    with pytest.raises(AnalysisNotFoundError):
        get_reviewable_analysis(
            run.analysis_id,
            checkpoint_path=checkpoint_path,
            tenant_id="tenant-b",
        )
