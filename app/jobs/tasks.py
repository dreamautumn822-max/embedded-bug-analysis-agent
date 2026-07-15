from time import perf_counter

from opentelemetry.context import attach, detach
from opentelemetry.propagate import extract

from app.graph.responses import analysis_job_response
from app.graph.review_workflow import (
    resume_reviewable_analysis,
    start_reviewable_analysis,
)
from app.jobs.models import StoredJob
from app.jobs.store import create_job_store
from app.observability.metrics import observe_queue_job
from app.observability.tracing import configure_worker_tracing, flush_tracing, start_span
from app.schemas.bug import AnalysisReviewRequest, BugAnalyzeRequest


def run_analysis_job(job_id: str) -> dict:
    configure_worker_tracing()
    store = create_job_store()
    record = store.get(job_id)
    if record.cancellation_requested:
        return store.update(job_id, status="cancelled").model_dump(mode="json")

    record = store.update(
        job_id,
        status="running",
        attempts=record.attempts + 1,
        error=None,
    )
    started_at = perf_counter()
    token = attach(extract(record.trace_context))
    try:
        with start_span(
            "queue.analyze",
            {
                "messaging.system": "redis-rq",
                "messaging.operation": "process",
                "job.id": job_id,
            },
        ) as span:
            request = BugAnalyzeRequest.model_validate(record.request_payload)
            run = start_reviewable_analysis(
                **request.model_dump(),
                analysis_id=record.analysis_id,
                tenant_id=record.tenant_id,
            )
            response = analysis_job_response(run).model_dump(mode="json")
            status = run.status
            span.set_attribute("job.status", status)
            updated = store.update(
                job_id,
                status=status,
                review_status=response["review_status"],
                review_payload=response["review_payload"],
                result=response["result"],
                error=response["error"],
            )
            observe_queue_job(
                operation="analyze",
                status=status,
                duration_seconds=perf_counter() - started_at,
            )
            return updated.model_dump(mode="json")
    except Exception as exc:
        observe_queue_job(
            operation="analyze",
            status="failed",
            duration_seconds=perf_counter() - started_at,
        )
        store.update(job_id, status="failed", error=_error_message(exc))
        raise
    finally:
        detach(token)
        flush_tracing()


def run_review_job(job_id: str) -> dict:
    configure_worker_tracing()
    store = create_job_store()
    record = store.get(job_id)
    if record.cancellation_requested:
        return store.update(job_id, status="cancelled").model_dump(mode="json")
    if record.review_request is None:
        raise ValueError("Queued review job has no review request")

    record = store.update(
        job_id,
        status="running",
        attempts=record.attempts + 1,
        error=None,
    )
    started_at = perf_counter()
    token = attach(extract(record.trace_context))
    try:
        with start_span(
            "queue.review",
            {
                "messaging.system": "redis-rq",
                "messaging.operation": "process",
                "job.id": job_id,
            },
        ) as span:
            review = AnalysisReviewRequest.model_validate(record.review_request)
            run = resume_reviewable_analysis(
                record.analysis_id,
                approved=review.approved,
                reviewer=review.reviewer,
                comment=review.comment,
                tenant_id=record.tenant_id,
            )
            response = analysis_job_response(run).model_dump(mode="json")
            span.set_attribute("job.status", run.status)
            span.set_attribute("job.review.approved", review.approved)
            updated = store.update(
                job_id,
                status=run.status,
                review_status=response["review_status"],
                review_payload=response["review_payload"],
                result=response["result"],
                error=response["error"],
            )
            observe_queue_job(
                operation="review",
                status=run.status,
                duration_seconds=perf_counter() - started_at,
            )
            return updated.model_dump(mode="json")
    except Exception as exc:
        observe_queue_job(
            operation="review",
            status="failed",
            duration_seconds=perf_counter() - started_at,
        )
        store.update(job_id, status="failed", error=_error_message(exc))
        raise
    finally:
        detach(token)
        flush_tracing()


def _error_message(exc: Exception) -> str:
    return f"{type(exc).__name__}: {str(exc)}"[-2000:]
