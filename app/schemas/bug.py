from pydantic import BaseModel, Field


class BugAnalyzeRequest(BaseModel):
    device_model: str = Field(min_length=1)
    firmware_version: str = Field(min_length=1)
    symptom: str = Field(min_length=1)
    logs: str = Field(min_length=1)
    stack_trace: str | None = None
    module_hint: str | None = None


class BugAnalyzeResponse(BaseModel):
    bug_type: str
    summary: str
    root_causes: list[str]
    evidence: list[str]
    fix_suggestions: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
