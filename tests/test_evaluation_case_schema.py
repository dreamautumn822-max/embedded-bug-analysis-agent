import copy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.evaluation.case_schema import validate_evaluation_cases


def _production_payload() -> list[dict]:
    payload = json.loads(
        Path("data/bugs/real_eval_cases.example.json").read_text(encoding="utf-8")
    )
    payload[0]["source_ticket_hash"] = (
        "sha256:" + hashlib.sha256(b"internal-ticket-001").hexdigest()
    )
    return payload


def test_synthetic_evaluation_dataset_passes_contract_validation():
    payload = json.loads(
        Path("data/bugs/eval_cases.json").read_text(encoding="utf-8")
    )

    cases = validate_evaluation_cases(payload)

    assert len(cases) == 5
    assert {case.case_origin for case in cases} == {"synthetic"}


def test_production_case_requires_adjudication_and_manual_review():
    payload = _production_payload()
    payload[0]["label_status"] = "draft"
    payload[0]["annotator_count"] = 1
    payload[0]["sanitization_actions"].remove("manual_review")

    with pytest.raises(ValidationError, match="two annotators"):
        validate_evaluation_cases(payload)


def test_production_case_rejects_sensitive_tokens():
    payload = _production_payload()
    payload[0]["logs"] = "peer 48:2c:a0:11:22:33 failed at 192.168.1.2"

    with pytest.raises(ValidationError, match="sensitive token types"):
        validate_evaluation_cases(payload)


def test_dataset_rejects_duplicate_case_ids():
    payload = json.loads(
        Path("data/bugs/eval_cases.json").read_text(encoding="utf-8")
    )
    payload.append(copy.deepcopy(payload[0]))

    with pytest.raises(ValueError, match="duplicate case_id"):
        validate_evaluation_cases(payload)


def test_production_template_hash_cannot_pass_strict_validation():
    payload = json.loads(
        Path("data/bugs/real_eval_cases.example.json").read_text(encoding="utf-8")
    )

    with pytest.raises(ValidationError, match="placeholder"):
        validate_evaluation_cases(payload, require_production=True)
