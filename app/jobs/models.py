from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


JobStatus = Literal[
    "queued",
    "running",
    "pending_review",
    "completed",
    "failed",
    "cancel_requested",
    "cancelled",
    "timed_out",
]
JobOperation = Literal["analyze", "review"]
TERMINAL_JOB_STATUSES = {"completed", "failed", "cancelled", "timed_out"}


class StoredJob(BaseModel):
    job_id: str
    analysis_id: str
    tenant_id: str
    status: JobStatus
    operation: JobOperation
    created_at: datetime
    updated_at: datetime
    timeout_seconds: int
    attempts: int = Field(default=0, ge=0)
    request_fingerprint: str
    request_payload: dict
    review_request: dict | None = None
    active_rq_job_id: str | None = None
    trace_context: dict[str, str] = Field(default_factory=dict)
    review_status: str = "not_assessed"
    review_payload: dict | None = None
    result: dict | None = None
    error: str | None = None
    cancellation_requested: bool = False

    @classmethod
    def create(
        cls,
        *,
        job_id: str,
        tenant_id: str,
        timeout_seconds: int,
        request_fingerprint: str,
        request_payload: dict,
        trace_context: dict[str, str],
    ) -> "StoredJob":
        now = datetime.now(timezone.utc)
        return cls(
            job_id=job_id,
            analysis_id=job_id,
            tenant_id=tenant_id,
            status="queued",
            operation="analyze",
            created_at=now,
            updated_at=now,
            timeout_seconds=timeout_seconds,
            request_fingerprint=request_fingerprint,
            request_payload=request_payload,
            trace_context=trace_context,
        )
