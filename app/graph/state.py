from typing import TypedDict


class BugAnalysisState(TypedDict):
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
    fix_suggestions: list[str]
    final_report: str
