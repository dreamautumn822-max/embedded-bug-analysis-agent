from fastapi import FastAPI

from app.graph.bug_analysis_graph import analyze_bug
from app.schemas.bug import BugAnalyzeRequest, BugAnalyzeResponse


app = FastAPI(title="Embedded Bug Analysis Agent")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=BugAnalyzeResponse)
def analyze(request: BugAnalyzeRequest) -> BugAnalyzeResponse:
    result = analyze_bug(
        device_model=request.device_model,
        firmware_version=request.firmware_version,
        symptom=request.symptom,
        logs=request.logs,
        stack_trace=request.stack_trace,
        module_hint=request.module_hint,
    )
    top_hypothesis = result["hypotheses"][0]

    return BugAnalyzeResponse(
        bug_type=result["bug_type"],
        summary=top_hypothesis["title"],
        root_causes=[top_hypothesis["description"]],
        evidence=result["evidence"],
        fix_suggestions=result["fix_suggestions"],
        confidence=top_hypothesis["confidence"],
    )
