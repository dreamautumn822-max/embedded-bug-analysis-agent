import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.evaluation.case_schema import dataset_summary, validate_evaluation_cases


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate evaluation case provenance, labels and sanitization.",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=PROJECT_ROOT / "data" / "bugs" / "eval_cases.json",
    )
    parser.add_argument(
        "--require-production",
        action="store_true",
        help="Fail unless at least one anonymized production case is present.",
    )
    args = parser.parse_args()

    try:
        payload = json.loads(args.cases.read_text(encoding="utf-8"))
        cases = validate_evaluation_cases(
            payload,
            require_production=args.require_production,
        )
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        print(f"dataset_validation=failed\nerror={exc}", file=sys.stderr)
        return 1

    print("dataset_validation=passed")
    print(json.dumps(dataset_summary(cases), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
