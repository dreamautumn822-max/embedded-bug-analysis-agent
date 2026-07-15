import pytest
from pydantic import ValidationError

from app.llm.schemas import LLMRootCauseResult


def test_llm_root_cause_result_accepts_valid_payload():
    result = LLMRootCauseResult.model_validate(
        {
            "hypotheses": [
                {
                    "title": "DHCP starts before bridge ready",
                    "description": "DHCP server restarts while br-lan is still blocking.",
                    "confidence": 0.91,
                    "evidence_ids": ["bug:BUG-018", "doc:dhcp.md::startup::000"],
                }
            ],
            "fix_suggestions": ["Wait for br-lan forwarding before restarting DHCP."],
        }
    )

    assert result.hypotheses[0].confidence == 0.91
    assert result.hypotheses[0].evidence_ids == [
        "bug:BUG-018",
        "doc:dhcp.md::startup::000",
    ]
    assert result.fix_suggestions == ["Wait for br-lan forwarding before restarting DHCP."]


def test_llm_root_cause_result_rejects_empty_hypotheses():
    with pytest.raises(ValidationError):
        LLMRootCauseResult.model_validate(
            {
                "hypotheses": [],
                "fix_suggestions": ["Collect more logs."],
            }
        )


def test_llm_root_cause_result_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        LLMRootCauseResult.model_validate(
            {
                "hypotheses": [
                    {
                        "title": "Bad confidence",
                        "description": "Confidence must be numeric and bounded.",
                        "confidence": 1.2,
                    }
                ],
                "fix_suggestions": ["Fix output schema."],
            }
        )
