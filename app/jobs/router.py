from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.jobs.service import (
    IdempotencyConflictError,
    JobStateConflictError,
    QueueUnavailableError,
    cancel_job,
    enqueue_analysis_job,
    enqueue_review_job,
    get_job,
    queued_job_response,
)
from app.jobs.store import StoredJobNotFoundError
from app.schemas.jobs import (
    QueuedAnalysisJobResponse,
    QueuedBugAnalyzeRequest,
    QueuedReviewRequest,
)
from app.security.auth import Principal, get_principal


router = APIRouter(prefix="/v1/jobs", tags=["queued-analysis"])


@router.post(
    "",
    response_model=QueuedAnalysisJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_queued_analysis(
    request: QueuedBugAnalyzeRequest,
    principal: Annotated[Principal, Depends(get_principal)],
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", max_length=200),
    ] = None,
) -> QueuedAnalysisJobResponse:
    try:
        record = enqueue_analysis_job(
            request,
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except JobStateConflictError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except QueueUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return queued_job_response(record)


@router.get("/{job_id}", response_model=QueuedAnalysisJobResponse)
def get_queued_analysis(
    job_id: str,
    principal: Annotated[Principal, Depends(get_principal)],
) -> QueuedAnalysisJobResponse:
    try:
        record = get_job(job_id, tenant_id=principal.tenant_id)
    except StoredJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    except QueueUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return queued_job_response(record)


@router.delete("/{job_id}", response_model=QueuedAnalysisJobResponse)
def cancel_queued_analysis(
    job_id: str,
    principal: Annotated[Principal, Depends(get_principal)],
) -> QueuedAnalysisJobResponse:
    try:
        record = cancel_job(job_id, tenant_id=principal.tenant_id)
    except StoredJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    except JobStateConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except QueueUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return queued_job_response(record)


@router.post(
    "/{job_id}/review",
    response_model=QueuedAnalysisJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def review_queued_analysis(
    job_id: str,
    request: QueuedReviewRequest,
    principal: Annotated[Principal, Depends(get_principal)],
) -> QueuedAnalysisJobResponse:
    try:
        record = enqueue_review_job(
            job_id,
            request,
            tenant_id=principal.tenant_id,
        )
    except StoredJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    except JobStateConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except QueueUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return queued_job_response(record)
