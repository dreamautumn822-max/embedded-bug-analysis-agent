import hashlib
import json
from uuid import uuid4

from opentelemetry.propagate import inject
from redis import Redis
from redis.exceptions import RedisError
from rq import Queue, Retry
from rq.command import send_stop_job_command
from rq.exceptions import NoSuchJobError
from rq.job import Job, JobStatus

from app.jobs.config import JobQueueSettings
from app.jobs.models import StoredJob, TERMINAL_JOB_STATUSES
from app.jobs.store import (
    JobStore,
    StoredJobNotFoundError,
    create_job_store,
    create_redis_connection,
)
from app.observability.metrics import (
    observe_queue_job,
    set_queue_depth,
    set_queue_status_counts,
)
from app.schemas.bug import AnalysisReviewRequest, BugAnalyzeRequest
from app.schemas.jobs import QueuedAnalysisJobResponse, QueuedBugAnalyzeRequest


class QueueUnavailableError(RuntimeError):
    pass


class JobStateConflictError(RuntimeError):
    pass


class IdempotencyConflictError(RuntimeError):
    pass


def enqueue_analysis_job(
    request: QueuedBugAnalyzeRequest,
    *,
    tenant_id: str,
    idempotency_key: str | None = None,
    connection: Redis | None = None,
) -> StoredJob:
    settings = JobQueueSettings.from_env()
    connection = connection or create_redis_connection(settings)
    _ensure_connection(connection)
    store = create_job_store(connection, settings)
    timeout_seconds = request.timeout_seconds or settings.timeout_seconds
    if timeout_seconds > settings.max_timeout_seconds:
        raise JobStateConflictError(
            f"timeout_seconds must not exceed {settings.max_timeout_seconds}"
        )
    request_payload = BugAnalyzeRequest.model_validate(
        request.model_dump(exclude={"timeout_seconds"})
    ).model_dump(mode="json")
    fingerprint = _request_fingerprint(tenant_id, request_payload)

    if idempotency_key:
        existing = store.get_idempotent_job(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
        )
        if existing:
            job_id, existing_fingerprint = existing
            if existing_fingerprint != fingerprint:
                raise IdempotencyConflictError(
                    "Idempotency key was already used with a different request"
                )
            return reconcile_job(store.get_for_tenant(job_id, tenant_id), connection)

    job_id = uuid4().hex
    trace_context: dict[str, str] = {}
    inject(trace_context)
    record = StoredJob.create(
        job_id=job_id,
        tenant_id=tenant_id,
        timeout_seconds=timeout_seconds,
        request_fingerprint=fingerprint,
        request_payload=request_payload,
        trace_context=trace_context,
    )
    if idempotency_key and not store.claim_idempotency_key(
        tenant_id=tenant_id,
        idempotency_key=idempotency_key,
        job_id=job_id,
        request_fingerprint=fingerprint,
    ):
        existing = store.get_idempotent_job(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
        )
        if existing is None:
            raise QueueUnavailableError("Unable to claim idempotency key")
        existing_job_id, existing_fingerprint = existing
        if existing_fingerprint != fingerprint:
            raise IdempotencyConflictError(
                "Idempotency key was already used with a different request"
            )
        return reconcile_job(
            store.get_for_tenant(existing_job_id, tenant_id),
            connection,
        )

    store.create(record)
    try:
        from app.jobs.tasks import run_analysis_job

        queue = Queue(settings.queue_name, connection=connection)
        rq_job = queue.enqueue_call(
            func=run_analysis_job,
            args=(job_id,),
            timeout=timeout_seconds,
            result_ttl=settings.result_ttl_seconds,
            failure_ttl=settings.failure_ttl_seconds,
            job_id=job_id,
            retry=_retry_policy(settings),
            description=f"Analyze bug job {job_id}",
        )
        record = store.update(job_id, active_rq_job_id=rq_job.id)
        _update_queue_depth(queue)
        observe_queue_job(operation="analyze", status="queued")
        return record
    except Exception as exc:
        store.update(job_id, status="failed", error=_error_message(exc))
        raise QueueUnavailableError(f"Unable to enqueue analysis: {exc}") from exc


def enqueue_review_job(
    job_id: str,
    request: AnalysisReviewRequest,
    *,
    tenant_id: str,
    connection: Redis | None = None,
) -> StoredJob:
    settings = JobQueueSettings.from_env()
    connection = connection or create_redis_connection(settings)
    _ensure_connection(connection)
    store = create_job_store(connection, settings)
    record = reconcile_job(store.get_for_tenant(job_id, tenant_id), connection)
    if record.status != "pending_review":
        raise JobStateConflictError("Job is not pending human review")

    rq_job_id = f"{job_id}-review-{uuid4().hex[:8]}"
    trace_context: dict[str, str] = {}
    inject(trace_context)
    record = store.update(
        job_id,
        status="queued",
        operation="review",
        review_request=request.model_dump(mode="json"),
        trace_context=trace_context,
        active_rq_job_id=rq_job_id,
        cancellation_requested=False,
        error=None,
    )
    try:
        from app.jobs.tasks import run_review_job

        queue = Queue(settings.queue_name, connection=connection)
        queue.enqueue_call(
            func=run_review_job,
            args=(job_id,),
            timeout=min(60, settings.max_timeout_seconds),
            result_ttl=settings.result_ttl_seconds,
            failure_ttl=settings.failure_ttl_seconds,
            job_id=rq_job_id,
            retry=_retry_policy(settings),
            description=f"Review bug job {job_id}",
        )
        _update_queue_depth(queue)
        observe_queue_job(operation="review", status="queued")
        return record
    except Exception as exc:
        store.update(job_id, status="failed", error=_error_message(exc))
        raise QueueUnavailableError(f"Unable to enqueue review: {exc}") from exc


def get_job(
    job_id: str,
    *,
    tenant_id: str,
    connection: Redis | None = None,
) -> StoredJob:
    settings = JobQueueSettings.from_env()
    connection = connection or create_redis_connection(settings)
    _ensure_connection(connection)
    store = create_job_store(connection, settings)
    return reconcile_job(store.get_for_tenant(job_id, tenant_id), connection)


def cancel_job(
    job_id: str,
    *,
    tenant_id: str,
    connection: Redis | None = None,
) -> StoredJob:
    settings = JobQueueSettings.from_env()
    connection = connection or create_redis_connection(settings)
    _ensure_connection(connection)
    store = create_job_store(connection, settings)
    record = reconcile_job(store.get_for_tenant(job_id, tenant_id), connection)
    if record.status in TERMINAL_JOB_STATUSES:
        raise JobStateConflictError(f"Job is already {record.status}")
    if record.status == "pending_review":
        observe_queue_job(operation=record.operation, status="cancelled")
        return store.update(
            job_id,
            status="cancelled",
            cancellation_requested=True,
        )

    if not record.active_rq_job_id:
        return store.update(
            job_id,
            status="cancelled",
            cancellation_requested=True,
        )
    try:
        rq_job = Job.fetch(record.active_rq_job_id, connection=connection)
        rq_status = rq_job.get_status(refresh=True)
    except NoSuchJobError:
        return store.update(
            job_id,
            status="cancelled",
            cancellation_requested=True,
        )

    if rq_status in {
        JobStatus.CREATED,
        JobStatus.QUEUED,
        JobStatus.DEFERRED,
        JobStatus.SCHEDULED,
    }:
        rq_job.cancel()
        status = "cancelled"
    elif rq_status == JobStatus.STARTED:
        send_stop_job_command(connection, rq_job.id)
        status = "cancel_requested"
    else:
        return reconcile_job(record, connection)

    observe_queue_job(operation=record.operation, status=status)
    return store.update(
        job_id,
        status=status,
        cancellation_requested=True,
    )


def reconcile_job(record: StoredJob, connection: Redis) -> StoredJob:
    if record.status in TERMINAL_JOB_STATUSES or record.status == "pending_review":
        return record
    if not record.active_rq_job_id:
        return record
    store = create_job_store(connection)
    try:
        rq_job = Job.fetch(record.active_rq_job_id, connection=connection)
        rq_status = rq_job.get_status(refresh=True)
    except NoSuchJobError:
        return record

    if rq_status in {JobStatus.CANCELED, JobStatus.STOPPED}:
        return store.update(
            record.job_id,
            status="cancelled",
            cancellation_requested=True,
        )
    if rq_status == JobStatus.FAILED:
        latest_result = rq_job.latest_result()
        exc_info = (
            latest_result.exc_string
            if latest_result is not None and latest_result.exc_string
            else "RQ job failed"
        )
        timed_out = "timeout" in exc_info.lower()
        return store.update(
            record.job_id,
            status="timed_out" if timed_out else "failed",
            error=_error_message(exc_info),
        )
    if rq_status in {JobStatus.QUEUED, JobStatus.DEFERRED, JobStatus.SCHEDULED}:
        if record.status not in {"queued", "cancel_requested"}:
            return store.update(record.job_id, status="queued")
    return record


def queue_health(connection: Redis | None = None) -> dict[str, object]:
    settings = JobQueueSettings.from_env()
    connection = connection or create_redis_connection(settings)
    try:
        connection.ping()
        queue = Queue(settings.queue_name, connection=connection)
        return {"status": "ok", "queue": settings.queue_name, "depth": len(queue)}
    except RedisError as exc:
        return {"status": "unavailable", "queue": settings.queue_name, "error": str(exc)}


def refresh_queue_metrics(connection: Redis | None = None) -> None:
    settings = JobQueueSettings.from_env()
    connection = connection or create_redis_connection(settings)
    try:
        queue = Queue(settings.queue_name, connection=connection)
        store = create_job_store(connection, settings)
        set_queue_depth(queue=settings.queue_name, depth=len(queue))
        set_queue_status_counts(store.status_counts())
    except RedisError:
        return


def queued_job_response(record: StoredJob) -> QueuedAnalysisJobResponse:
    return QueuedAnalysisJobResponse(
        job_id=record.job_id,
        analysis_id=record.analysis_id,
        status=record.status,
        operation=record.operation,
        created_at=record.created_at,
        updated_at=record.updated_at,
        attempts=record.attempts,
        timeout_seconds=record.timeout_seconds,
        review_status=record.review_status,
        review_payload=record.review_payload,
        result=record.result,
        error=record.error,
        cancellation_requested=record.cancellation_requested,
        poll_url=f"/v1/jobs/{record.job_id}",
    )


def _request_fingerprint(tenant_id: str, request_payload: dict) -> str:
    canonical = json.dumps(request_payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(f"{tenant_id}\0{canonical}".encode("utf-8")).hexdigest()


def _retry_policy(settings: JobQueueSettings) -> Retry | None:
    if settings.max_retries == 0:
        return None
    intervals = [min(30, 5 * (index + 1)) for index in range(settings.max_retries)]
    return Retry(max=settings.max_retries, interval=intervals)


def _ensure_connection(connection: Redis) -> None:
    try:
        connection.ping()
    except RedisError as exc:
        raise QueueUnavailableError(f"Redis is unavailable: {exc}") from exc


def _update_queue_depth(queue: Queue) -> None:
    set_queue_depth(queue=queue.name, depth=len(queue))


def _error_message(error: object) -> str:
    text = str(error).strip().replace("\x00", "")
    return text[-2000:] if text else type(error).__name__
