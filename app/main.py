from time import perf_counter
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST

from app.graph.bug_analysis_graph import analyze_bug
from app.graph.review_workflow import (
    AnalysisNotFoundError,
    AnalysisNotPendingReviewError,
    get_reviewable_analysis,
    resume_reviewable_analysis,
    start_reviewable_analysis,
)
from app.graph.responses import analysis_job_response, bug_response
from app.jobs.router import router as jobs_router
from app.jobs.service import queue_health, refresh_queue_metrics
from app.rag.config import RAGSettings
from app.observability.metrics import (
    observe_analysis,
    generate_metrics_payload,
    observe_http,
    observe_human_review,
)
from app.observability.tracing import configure_tracing
from app.schemas.bug import (
    AnalysisJobResponse,
    AnalysisReviewRequest,
    BugAnalyzeRequest,
    BugAnalyzeResponse,
)
from app.security.auth import Principal, current_auth_settings, get_principal


app = FastAPI(title="Embedded Bug Analysis Agent")
app.include_router(jobs_router)


@app.middleware("http")
async def prometheus_http_middleware(request: Request, call_next):
    started_at = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        if request.url.path != "/metrics":
            route_object = request.scope.get("route")
            route = getattr(route_object, "path", request.url.path)
            observe_http(
                method=request.method,
                route=route,
                status_code=status_code,
                duration_seconds=perf_counter() - started_at,
            )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/details")
def health_details() -> dict[str, object]:
    settings = RAGSettings.from_env()
    queue = queue_health()
    return {
        "status": "ok",
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "retrieval_mode": settings.retrieval_mode,
        "rerank_provider": settings.rerank_provider,
        "git_history_enabled": settings.git_history_enabled,
        "queue": queue,
        "authentication_enabled": current_auth_settings().enabled,
    }


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    refresh_queue_metrics()
    return Response(content=generate_metrics_payload(), media_type=CONTENT_TYPE_LATEST)


@app.post("/analyze", response_model=BugAnalyzeResponse)
def analyze(
    request: BugAnalyzeRequest,
    principal: Annotated[Principal, Depends(get_principal)],
) -> BugAnalyzeResponse:
    started_at = perf_counter()
    result = analyze_bug(
        device_model=request.device_model,
        firmware_version=request.firmware_version,
        symptom=request.symptom,
        logs=request.logs,
        stack_trace=request.stack_trace,
        module_hint=request.module_hint,
        tenant_id=principal.tenant_id,
    )
    response = bug_response(result)
    observe_analysis(
        workflow="synchronous",
        status="completed",
        generation_mode=response.generation_mode,
        review_status=response.review_status,
        duration_seconds=perf_counter() - started_at,
    )
    return response


@app.post("/analyses", response_model=AnalysisJobResponse)
def create_analysis(
    request: BugAnalyzeRequest,
    principal: Annotated[Principal, Depends(get_principal)],
) -> AnalysisJobResponse:
    started_at = perf_counter()
    run = start_reviewable_analysis(
        device_model=request.device_model,
        firmware_version=request.firmware_version,
        symptom=request.symptom,
        logs=request.logs,
        stack_trace=request.stack_trace,
        module_hint=request.module_hint,
        tenant_id=principal.tenant_id,
    )
    response = analysis_job_response(run)
    observe_analysis(
        workflow="persistent",
        status=run.status,
        generation_mode=run.state.get("generation_mode", "unknown"),
        review_status=run.state.get("review_status", "unknown"),
        duration_seconds=perf_counter() - started_at,
    )
    return response


@app.get("/analyses/{analysis_id}", response_model=AnalysisJobResponse)
def get_analysis(
    analysis_id: str,
    principal: Annotated[Principal, Depends(get_principal)],
) -> AnalysisJobResponse:
    try:
        run = get_reviewable_analysis(
            analysis_id,
            tenant_id=principal.tenant_id,
        )
    except AnalysisNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Analysis not found") from exc
    return analysis_job_response(run)


@app.post(
    "/analyses/{analysis_id}/review",
    response_model=AnalysisJobResponse,
)
def review_analysis(
    analysis_id: str,
    request: AnalysisReviewRequest,
    principal: Annotated[Principal, Depends(get_principal)],
) -> AnalysisJobResponse:
    started_at = perf_counter()
    try:
        run = resume_reviewable_analysis(
            analysis_id,
            approved=request.approved,
            reviewer=request.reviewer,
            comment=request.comment,
            tenant_id=principal.tenant_id,
        )
    except AnalysisNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Analysis not found") from exc
    except AnalysisNotPendingReviewError as exc:
        raise HTTPException(
            status_code=409,
            detail="Analysis is not pending human review",
        ) from exc
    response = analysis_job_response(run)
    observe_human_review(
        approved=request.approved,
        status=run.status,
        duration_seconds=perf_counter() - started_at,
    )
    return response


configure_tracing(app)
