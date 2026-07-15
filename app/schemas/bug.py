from typing import Literal

from pydantic import BaseModel, Field


class BugAnalyzeRequest(BaseModel):
    device_model: str = Field(min_length=1)
    firmware_version: str = Field(min_length=1)
    symptom: str = Field(min_length=1)
    logs: str = Field(min_length=1)
    stack_trace: str | None = None
    module_hint: str | None = None


class RootCauseHypothesis(BaseModel):
    title: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)


class EvidenceDetail(BaseModel):
    evidence_id: str
    evidence_type: Literal["log", "doc", "bug", "code", "other"]
    source: str
    content: str
    score: float | None = None
    rank: int | None = None
    section: str | None = None
    chunk_id: str | None = None
    symbol: str | None = None
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    code_kind: str | None = None
    calls: list[str] = Field(default_factory=list)
    callers: list[str] = Field(default_factory=list)
    preprocessor_context: str | None = None
    repository_revision: str | None = None
    commit_sha: str | None = None
    commit_subject: str | None = None
    commit_date: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    retrieval_method: str | None = None
    rerank_method: str | None = None
    vector_score: float | None = None
    vector_rank: int | None = None
    bm25_score: float | None = None
    bm25_rank: int | None = None
    fusion_score: float | None = None
    rerank_score: float | None = None


class TraceEvent(BaseModel):
    node: str
    status: Literal["success", "fallback"]
    duration_ms: float = Field(ge=0.0)
    output_count: int = Field(ge=0)
    fallback_count: int = Field(ge=0)


class FallbackReason(BaseModel):
    node: str
    code: str
    message: str
    error_type: str | None = None


class ReviewDecision(BaseModel):
    approved: bool
    reviewer: str = Field(min_length=1, max_length=100)
    comment: str | None = Field(default=None, max_length=2000)


class HumanReviewPayload(BaseModel):
    kind: Literal["bug_analysis_review"]
    bug_type: str
    generation_mode: Literal["llm", "rule"]
    confidence: float = Field(ge=0.0, le=1.0)
    review_reasons: list[str] = Field(default_factory=list)
    top_hypothesis: RootCauseHypothesis | None = None
    evidence_preview: list[EvidenceDetail] = Field(default_factory=list)


class BugAnalyzeResponse(BaseModel):
    bug_type: str
    summary: str
    root_causes: list[str]
    hypotheses: list[RootCauseHypothesis] = Field(default_factory=list)
    evidence: list[str]
    evidence_details: list[EvidenceDetail] = Field(default_factory=list)
    fix_suggestions: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    generation_mode: Literal["llm", "rule"]
    trace_events: list[TraceEvent] = Field(default_factory=list)
    fallback_reasons: list[FallbackReason] = Field(default_factory=list)
    review_required: bool = False
    review_status: Literal[
        "not_required",
        "pending",
        "approved",
        "rejected",
    ] = "not_required"
    review_reasons: list[str] = Field(default_factory=list)
    review_decision: ReviewDecision | None = None


class AnalysisReviewRequest(BaseModel):
    approved: bool
    reviewer: str = Field(min_length=1, max_length=100)
    comment: str | None = Field(default=None, max_length=2000)


class AnalysisJobResponse(BaseModel):
    analysis_id: str
    status: Literal["pending_review", "completed", "failed"]
    review_status: Literal[
        "not_assessed",
        "not_required",
        "pending",
        "approved",
        "rejected",
    ]
    review_payload: HumanReviewPayload | None = None
    result: BugAnalyzeResponse | None = None
    error: str | None = None
