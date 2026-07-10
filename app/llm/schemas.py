from pydantic import BaseModel, Field


class LLMHypothesis(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class LLMRootCauseResult(BaseModel):
    hypotheses: list[LLMHypothesis] = Field(min_length=1)
    fix_suggestions: list[str] = Field(min_length=1)
