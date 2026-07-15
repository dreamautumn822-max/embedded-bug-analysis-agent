import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.evaluation.case_schema import dataset_summary, validate_evaluation_cases
from app.evaluation.intake import import_production_cases


DEFAULT_OUTPUT = PROJECT_ROOT / "run" / "private_eval" / "real_eval_cases.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Anonymize, adjudicate and validate production bug cases.",
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--salt-env", default="BUG_AGENT_CASE_HASH_SALT")
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    salt = os.getenv(args.salt_env, "")
    try:
        _validate_output_path(args.output.resolve())
        raw_payload = json.loads(args.input.read_text(encoding="utf-8"))
        imported = import_production_cases(raw_payload, hash_salt=salt)
        combined = [case.model_dump(mode="json") for case in imported]
        if args.append and args.output.exists():
            existing = json.loads(args.output.read_text(encoding="utf-8"))
            combined = [*existing, *combined]
        validated = validate_evaluation_cases(combined, require_production=True)
        _atomic_write_json(
            args.output,
            [case.model_dump(mode="json") for case in validated],
        )
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        print(f"case_import=failed\nerror={exc}", file=sys.stderr)
        return 1

    print("case_import=passed")
    print(f"output={args.output.resolve()}")
    print(json.dumps(dataset_summary(validated), ensure_ascii=False, indent=2))
    return 0


def _validate_output_path(output_path: Path) -> None:
    private_root = DEFAULT_OUTPUT.parent.resolve()
    if output_path.is_relative_to(PROJECT_ROOT) and not output_path.is_relative_to(
        private_root
    ):
        raise ValueError(
            "Production cases inside the repository must stay under run/private_eval"
        )


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
