import json

import pytest
from pydantic import ValidationError

from app.evaluation.intake import (
    RawProductionCase,
    import_production_cases,
    sanitize_case_text,
)


def _raw_case() -> dict:
    return {
        "source_ticket_id": "TICKET-001",
        "device_model": "ONU serial=ABC12345",
        "firmware_version": "v1.0",
        "symptom": "account=customer-a cannot connect",
        "logs": (
            "peer 10.1.2.3 mac 00:11:22:33:44:55 "
            "email owner@example.com hostname=edge-01"
        ),
        "module_hint": "network_dhcp",
        "annotations": [
            {
                "annotator_ref": "a",
                "expected_bug_type": "network_dhcp",
                "expected_root_cause_keywords": ["bridge"],
                "expected_review_required": False,
            },
            {
                "annotator_ref": "b",
                "expected_bug_type": "network_dhcp",
                "expected_root_cause_keywords": ["lease"],
                "expected_review_required": False,
            },
        ],
        "adjudication": {
            "adjudicator_ref": "c",
            "expected_bug_type": "network_dhcp",
            "expected_root_cause_keywords": ["bridge", "lease"],
            "expected_evidence_terms": ["dhcp"],
            "expected_review_required": False,
        },
        "manual_review_confirmed": True,
    }


def test_import_production_cases_anonymizes_and_hashes_ticket():
    cases = import_production_cases([_raw_case()], hash_salt="a-secure-test-salt")

    case = cases[0]
    serialized = json.dumps(case.model_dump(mode="json"), ensure_ascii=False)
    assert case.case_id.startswith("prod-")
    assert case.source_ticket_hash.startswith("sha256:")
    assert "TICKET-001" not in serialized
    assert "10.1.2.3" not in serialized
    assert "00:11:22:33:44:55" not in serialized
    assert "owner@example.com" not in serialized
    assert set(case.sanitization_actions) >= {
        "manual_review",
        "ip_address",
        "mac_address",
        "email",
        "serial_number",
        "account",
        "hostname",
    }


def test_sanitize_case_text_preserves_field_prefixes():
    sanitized, actions = sanitize_case_text(
        "serial=ABC123 account=user-a hostname=edge-01"
    )

    assert "serial=<DEVICE_SN_1>" in sanitized
    assert "account=<ACCOUNT_1>" in sanitized
    assert "hostname=<HOST_1>" in sanitized
    assert actions == {"serial_number", "account", "hostname"}


def test_case_sanitizer_preserves_same_and_different_ip_relationships():
    from app.evaluation.intake import CaseSanitizer

    sanitizer = CaseSanitizer()
    first, _ = sanitizer.sanitize("peer 10.1.2.3 via 10.1.2.4")
    second, _ = sanitizer.sanitize("retry peer 10.1.2.3")

    assert first == "peer <IP_1> via <IP_2>"
    assert second == "retry peer <IP_1>"


def test_raw_case_requires_independent_adjudicator():
    payload = _raw_case()
    payload["adjudication"]["adjudicator_ref"] = "a"

    with pytest.raises(ValidationError, match="adjudicator"):
        RawProductionCase.model_validate(payload)


def test_import_rejects_short_hash_salt():
    with pytest.raises(ValueError, match="at least 16"):
        import_production_cases([_raw_case()], hash_salt="short")
