from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.bug import (
    AnalysisReviewRequest,
    BugAnalyzeRequest,
    BugAnalyzeResponse,
    HumanReviewPayload,
)


class QueuedBugAnalyzeRequest(BugAnalyzeRequest):
    timeout_seconds: int | None = Field(default=None, ge=5, le=3600)


class QueuedAnalysisJobResponse(BaseModel):
    job_id: str
    analysis_id: str
    status: Literal[
        "queued",
        "running",
        "pending_review",
        "completed",
        "failed",
        "cancel_requested",
        "cancelled",
        "timed_out",
    ]
    operation: Literal["analyze", "review"]
    created_at: datetime
    updated_at: datetime
    attempts: int = Field(ge=0)
    timeout_seconds: int = Field(ge=1)
    review_status: str
    review_payload: HumanReviewPayload | None = None
    result: BugAnalyzeResponse | None = None
    error: str | None = None
    cancellation_requested: bool = False
    poll_url: str


class QueuedReviewRequest(AnalysisReviewRequest):
    pass
