import json
from pathlib import Path

from app.tools.log_parser import parse_syslog


EVAL_CASES_PATH = Path("data/bugs/eval_cases.json")
ALLOWED_BUG_TYPES = {
    "network_dhcp",
    "network_pppoe",
    "wifi_disconnect",
    "management_tr069",
    "unknown",
}
REQUIRED_FIELDS = {
    "case_id",
    "device_model",
    "firmware_version",
    "symptom",
    "logs",
    "expected_bug_type",
    "case_origin",
    "split",
    "label_status",
}


def test_eval_dataset_has_complete_cases_for_supported_and_review_paths():
    cases = json.loads(EVAL_CASES_PATH.read_text(encoding="utf-8"))

    assert isinstance(cases, list)
    assert len(cases) == 5
    assert {case["case_id"] for case in cases} == {
        "EVAL-001",
        "EVAL-002",
        "EVAL-003",
        "EVAL-004",
        "EVAL-005",
    }

    for case in cases:
        assert isinstance(case, dict)
        assert REQUIRED_FIELDS <= case.keys()
        for field in REQUIRED_FIELDS:
            assert case[field]
        assert case["expected_bug_type"] in ALLOWED_BUG_TYPES
        assert case["case_origin"] == "synthetic"


def test_eval_logs_are_parseable_and_have_evidence():
    cases = json.loads(EVAL_CASES_PATH.read_text(encoding="utf-8"))

    for case in cases:
        parsed = parse_syslog(case["logs"])

        assert parsed["modules"], case["case_id"]
        assert parsed["error_patterns"], case["case_id"]
        assert parsed["events"], case["case_id"]
        assert parsed["evidence"], case["case_id"]
