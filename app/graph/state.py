from typing import TypedDict


class BugAnalysisState(TypedDict):
    tenant_id: str
    device_model: str
    firmware_version: str
    symptom: str
    logs: str
    stack_trace: str | None
    module_hint: str | None
    extracted_info: dict
    bug_type: str
    related_docs: list[dict]
    related_bugs: list[dict]
    related_code: list[dict]
    parsed_logs: dict
    hypotheses: list[dict]
    evidence: list[str]
    evidence_details: list[dict]
    fix_suggestions: list[str]
    final_report: str
    generation_mode: str
    fallback_reasons: list[dict]
    trace_events: list[dict]
    review_required: bool
    review_status: str
    review_reasons: list[str]
    interactive_review: bool
    review_decision: dict | None
