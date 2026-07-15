from app.graph.review_workflow import AnalysisRun
from app.schemas.bug import AnalysisJobResponse, BugAnalyzeResponse


def bug_response(result: dict) -> BugAnalyzeResponse:
    top_hypothesis = result["hypotheses"][0]
    return BugAnalyzeResponse(
        bug_type=result["bug_type"],
        summary=top_hypothesis["title"],
        root_causes=[top_hypothesis["description"]],
        hypotheses=result["hypotheses"],
        evidence=result["evidence"],
        evidence_details=result["evidence_details"],
        fix_suggestions=result["fix_suggestions"],
        confidence=top_hypothesis["confidence"],
        generation_mode=result["generation_mode"],
        trace_events=result["trace_events"],
        fallback_reasons=result["fallback_reasons"],
        review_required=result["review_required"],
        review_status=result["review_status"],
        review_reasons=result["review_reasons"],
        review_decision=result.get("review_decision"),
    )


def analysis_job_response(run: AnalysisRun) -> AnalysisJobResponse:
    result = bug_response(run.state) if run.status == "completed" else None
    return AnalysisJobResponse(
        analysis_id=run.analysis_id,
        status=run.status,
        review_status=run.state.get("review_status", "not_assessed"),
        review_payload=run.review_payload,
        result=result,
        error=run.error,
    )
