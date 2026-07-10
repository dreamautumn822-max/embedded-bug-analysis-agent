from scripts.evaluate import (
    evaluate_case_result,
    normalize_text,
    summarize_stability,
)


def test_normalize_text_is_case_insensitive_and_space_tolerant():
    assert normalize_text(" DHCP  Bridge\nREADY ") == "dhcp bridge ready"


def test_evaluate_case_result_scores_expected_terms():
    case = {
        "case_id": "EVAL-X",
        "expected_bug_type": "network_dhcp",
        "expected_root_cause_keywords": ["DHCP", "bridge ready"],
        "expected_evidence_terms": ["BUG-018", "dhcp.md"],
    }
    result = {
        "bug_type": "network_dhcp",
        "hypotheses": [
            {
                "title": "DHCP service starts before bridge ready",
                "description": "The bridge ready event is not awaited.",
                "confidence": 0.91,
            }
        ],
        "evidence": [
            "bug: BUG-018 - DHCP service starts before bridge interface is ready",
            "doc: dhcp.md - DHCP module guide",
        ],
    }

    score = evaluate_case_result(case, result, parser_ok=True)

    assert score["classification_ok"] is True
    assert score["parser_ok"] is True
    assert score["root_cause_ok"] is True
    assert score["evidence_ok"] is True


def test_evaluate_case_result_detects_missing_root_cause_keyword():
    case = {
        "case_id": "EVAL-X",
        "expected_bug_type": "network_dhcp",
        "expected_root_cause_keywords": ["bridge ready"],
        "expected_evidence_terms": ["BUG-018"],
    }
    result = {
        "bug_type": "network_dhcp",
        "hypotheses": [
            {
                "title": "DHCP pool migration issue",
                "description": "The config key was not migrated.",
                "confidence": 0.6,
            }
        ],
        "evidence": ["bug: BUG-018 - DHCP service starts before bridge interface is ready"],
    }

    score = evaluate_case_result(case, result, parser_ok=True)

    assert score["classification_ok"] is True
    assert score["root_cause_ok"] is False
    assert score["evidence_ok"] is True


def test_summarize_stability_requires_same_bug_type_and_root_cause_hit():
    runs = [
        {"classification_ok": True, "root_cause_ok": True, "predicted_bug_type": "network_dhcp"},
        {"classification_ok": True, "root_cause_ok": True, "predicted_bug_type": "network_dhcp"},
    ]

    assert summarize_stability(runs) is True


def test_summarize_stability_fails_when_bug_type_changes():
    runs = [
        {"classification_ok": True, "root_cause_ok": True, "predicted_bug_type": "network_dhcp"},
        {"classification_ok": False, "root_cause_ok": True, "predicted_bug_type": "unknown"},
    ]

    assert summarize_stability(runs) is False
