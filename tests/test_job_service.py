from pathlib import Path
from time import sleep

import fakeredis
import pytest
from rq import Queue, SimpleWorker

from app.jobs import tasks
from app.jobs.config import JobQueueSettings
from app.jobs.models import StoredJob
from app.jobs.service import (
    IdempotencyConflictError,
    cancel_job,
    enqueue_analysis_job,
    enqueue_review_job,
    get_job,
    reconcile_job,
)
from app.jobs.store import StoredJobNotFoundError, create_job_store
from app.rag.retriever import clear_vector_store_cache
from app.schemas.bug import AnalysisReviewRequest
from app.schemas.jobs import QueuedBugAnalyzeRequest


def slow_test_job() -> None:
    sleep(2)


def _configure(monkeypatch, tmp_path: Path) -> JobQueueSettings:
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv(
        "LANGGRAPH_CHECKPOINT_PATH",
        str(tmp_path / "checkpoints.sqlite"),
    )
    monkeypatch.setenv("JOB_QUEUE_NAME", "test-bug-analysis")
    monkeypatch.setenv("JOB_MAX_RETRIES", "0")
    clear_vector_store_cache()
    return JobQueueSettings.from_env()


def _unknown_request() -> QueuedBugAnalyzeRequest:
    return QueuedBugAnalyzeRequest(
        device_model="Unknown Gateway",
        firmware_version="v0",
        symptom="unclassified intermittent issue",
        logs="daemon: unexplained status code 777",
    )


def test_queued_analysis_pauses_then_resumes_review(monkeypatch, tmp_path: Path):
    settings = _configure(monkeypatch, tmp_path)
    connection = fakeredis.FakeRedis()
    store = create_job_store(connection, settings)
    monkeypatch.setattr(tasks, "create_job_store", lambda: store)

    queued = enqueue_analysis_job(
        _unknown_request(),
        tenant_id="tenant-a",
        idempotency_key="case-001",
        connection=connection,
    )
    worker = SimpleWorker(
        [Queue(settings.queue_name, connection=connection)],
        connection=connection,
    )
    assert worker.work(burst=True, with_scheduler=False, logging_level="WARNING")

    pending = get_job(queued.job_id, tenant_id="tenant-a", connection=connection)
    assert pending.status == "pending_review"
    assert pending.review_payload["kind"] == "bug_analysis_review"
    with pytest.raises(StoredJobNotFoundError):
        get_job(queued.job_id, tenant_id="tenant-b", connection=connection)

    enqueue_review_job(
        queued.job_id,
        AnalysisReviewRequest(
            approved=True,
            reviewer="qa-owner",
            comment="approved after collecting evidence",
        ),
        tenant_id="tenant-a",
        connection=connection,
    )
    assert worker.work(burst=True, with_scheduler=False, logging_level="WARNING")

    completed = get_job(queued.job_id, tenant_id="tenant-a", connection=connection)
    assert completed.status == "completed"
    assert completed.review_status == "approved"
    assert completed.result["review_decision"]["reviewer"] == "qa-owner"
    assert completed.attempts == 2


def test_idempotency_and_queued_cancellation(monkeypatch, tmp_path: Path):
    _configure(monkeypatch, tmp_path)
    connection = fakeredis.FakeRedis()
    request = _unknown_request()

    first = enqueue_analysis_job(
        request,
        tenant_id="tenant-a",
        idempotency_key="same-request",
        connection=connection,
    )
    duplicate = enqueue_analysis_job(
        request,
        tenant_id="tenant-a",
        idempotency_key="same-request",
        connection=connection,
    )
    assert duplicate.job_id == first.job_id

    changed = request.model_copy(update={"logs": "different input"})
    with pytest.raises(IdempotencyConflictError):
        enqueue_analysis_job(
            changed,
            tenant_id="tenant-a",
            idempotency_key="same-request",
            connection=connection,
        )

    cancelled = cancel_job(
        first.job_id,
        tenant_id="tenant-a",
        connection=connection,
    )
    assert cancelled.status == "cancelled"
    assert cancelled.cancellation_requested is True


def test_reconcile_maps_rq_timeout_to_domain_status(monkeypatch, tmp_path: Path):
    settings = _configure(monkeypatch, tmp_path)
    connection = fakeredis.FakeRedis()
    store = create_job_store(connection, settings)
    record = StoredJob.create(
        job_id="timeout-domain-job",
        tenant_id="tenant-a",
        timeout_seconds=1,
        request_fingerprint="timeout",
        request_payload={},
        trace_context={},
    )
    store.create(record)
    queue = Queue(settings.queue_name, connection=connection)
    rq_job = queue.enqueue_call(
        slow_test_job,
        timeout=1,
        job_id="timeout-rq-job",
        failure_ttl=3600,
    )
    record = store.update(record.job_id, active_rq_job_id=rq_job.id)
    worker = SimpleWorker([queue], connection=connection)
    worker.work(burst=True, with_scheduler=False, logging_level="WARNING")

    reconciled = reconcile_job(record, connection)

    assert reconciled.status == "timed_out"
    assert "timeout" in reconciled.error.lower()
