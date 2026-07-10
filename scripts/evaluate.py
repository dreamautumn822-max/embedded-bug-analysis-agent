import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.graph.bug_analysis_graph import analyze_bug
from app.tools.log_parser import parse_syslog


EVAL_CASES_PATH = PROJECT_ROOT / "data" / "bugs" / "eval_cases.json"


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def evaluate_case_result(case: dict[str, Any], result: dict[str, Any], parser_ok: bool) -> dict[str, Any]:
    expected = case["expected_bug_type"]
    predicted = result["bug_type"]
    root_text = normalize_text(
        " ".join(
            [
                hypothesis.get("title", "") + " " + hypothesis.get("description", "")
                for hypothesis in result.get("hypotheses", [])
            ]
        )
    )
    evidence_text = normalize_text(" ".join(result.get("evidence", [])))

    root_keywords = case.get("expected_root_cause_keywords", [])
    evidence_terms = case.get("expected_evidence_terms", [])

    return {
        "case_id": case["case_id"],
        "predicted_bug_type": predicted,
        "expected_bug_type": expected,
        "classification_ok": predicted == expected,
        "parser_ok": parser_ok,
        "root_cause_ok": _all_terms_present(root_text, root_keywords),
        "evidence_ok": _all_terms_present(evidence_text, evidence_terms)
        if evidence_terms
        else bool(result.get("evidence")),
    }


def summarize_stability(runs: list[dict[str, Any]]) -> bool:
    if not runs:
        return False
    bug_types = {run["predicted_bug_type"] for run in runs}
    return len(bug_types) == 1 and all(run["classification_ok"] and run["root_cause_ok"] for run in runs)


def run_evaluation(cases: list[dict[str, Any]], repeat: int) -> dict[str, Any]:
    scores: list[dict[str, Any]] = []
    stable_cases = 0

    for case in cases:
        parsed = parse_syslog(case["logs"])
        parser_ok = bool(
            parsed["modules"] and parsed["error_patterns"] and parsed["events"] and parsed["evidence"]
        )
        case_runs = []

        for run_index in range(repeat):
            result = analyze_bug(
                device_model=case["device_model"],
                firmware_version=case["firmware_version"],
                symptom=case["symptom"],
                logs=case["logs"],
                stack_trace=None,
                module_hint=None,
            )
            score = evaluate_case_result(case, result, parser_ok)
            score["run_index"] = run_index + 1
            scores.append(score)
            case_runs.append(score)
            print(
                f"{case['case_id']}#run{run_index + 1}: "
                f"predicted={score['predicted_bug_type']}, "
                f"expected={score['expected_bug_type']}, "
                f"classification_ok={score['classification_ok']}, "
                f"parser_ok={score['parser_ok']}, "
                f"root_cause_ok={score['root_cause_ok']}, "
                f"evidence_ok={score['evidence_ok']}"
            )

        stable_cases += int(summarize_stability(case_runs))

    return {
        "case_count": len(cases),
        "run_count": len(scores),
        "repeat": repeat,
        "classification_accuracy": _rate(scores, "classification_ok"),
        "parser_coverage": _rate(scores, "parser_ok"),
        "root_cause_hit_rate": _rate(scores, "root_cause_ok"),
        "evidence_coverage": _rate(scores, "evidence_ok"),
        "output_stability": stable_cases / len(cases),
    }


def main() -> None:
    args = _parse_args()
    if args.load_env:
        load_dotenv(PROJECT_ROOT / ".env", override=True)
    if args.disable_llm:
        os.environ["LLM_ENABLED"] = "false"

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if not cases:
        raise SystemExit("No evaluation cases found.")

    summary = run_evaluation(cases, repeat=args.repeat)
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"{key}={value:.2f}")
        else:
            print(f"{key}={value}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate embedded bug analysis Agent.")
    parser.add_argument("--cases", type=Path, default=EVAL_CASES_PATH)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--load-env", action="store_true", help="Load .env before running evaluation.")
    parser.add_argument(
        "--disable-llm",
        action="store_true",
        help="Force LLM_ENABLED=false for deterministic rule-chain evaluation.",
    )
    args = parser.parse_args()
    if args.repeat < 1:
        raise SystemExit("--repeat must be >= 1")
    return args


def _all_terms_present(text: str, terms: list[str]) -> bool:
    return all(normalize_text(term) in text for term in terms)


def _rate(scores: list[dict[str, Any]], key: str) -> float:
    return sum(int(score[key]) for score in scores) / len(scores)


if __name__ == "__main__":
    main()
